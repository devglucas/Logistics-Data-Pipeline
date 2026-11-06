-- Accumulating snapshot: uma linha por remessa, reconstruída com todos os eventos conhecidos.
-- Como parte de TODOS os eventos da remessa (e não só os do lote), a ordem de chegada dos
-- lotes não muda o resultado: um evento atrasado apenas corrige os marcos.
DELETE FROM fato_entrega WHERE remessa_id IN (SELECT remessa_id FROM stg_afetadas);

INSERT INTO fato_entrega
WITH eventos AS (
    SELECT e.*,
           -- último evento relevante da remessa; empate no mesmo instante resolve pelo id
           ROW_NUMBER() OVER (PARTITION BY e.remessa_id ORDER BY e.ocorrido_em_utc DESC, e.evento_id DESC) AS ordem_inversa
    FROM fato_evento e
    WHERE e.remessa_id IN (SELECT remessa_id FROM stg_afetadas)
),
marcos AS (
    SELECT remessa_id,
           MIN(CASE WHEN codigo = 'COLETADO' THEN ocorrido_em_utc END)     AS coletado_em_utc,
           MIN(CASE WHEN codigo = 'SAIU_ENTREGA' THEN ocorrido_em_utc END) AS saiu_entrega_utc,
           MIN(CASE WHEN codigo = 'ENTREGUE' THEN ocorrido_em_utc END)     AS entregue_em_utc,
           MIN(CASE WHEN codigo = 'ENTREGUE' THEN data_local END)          AS data_entrega_local,
           SUM(codigo = 'TENTATIVA_FALHA')                                 AS tentativas_falhas,
           MAX(codigo = 'EXTRAVIADO')                                      AS extraviado,
           MAX(codigo = 'DEVOLVIDO')                                       AS devolvido,
           COUNT(*)                                                        AS qtd_eventos,
           MAX(ocorrido_em_utc)                                            AS ultimo_evento_utc
    FROM eventos
    GROUP BY remessa_id
),
chegada AS (
    SELECT e.remessa_id, MIN(e.ocorrido_em_utc) AS chegada_destino_utc
    FROM eventos e
    JOIN remessa r USING (remessa_id)
    WHERE e.codigo = 'RECEBIDO_HUB' AND e.hub_id = r.hub_destino
    GROUP BY e.remessa_id
),
base AS (
    SELECT r.remessa_id, r.cliente_id, r.servico, r.hub_origem, r.hub_destino, r.peso_kg, r.valor_frete,
           r.data_postagem_local, r.postado_em_utc, s.prazo_dias_uteis,
           -- prazo em dias úteis sem laço: soma N à sequência de dias úteis e volta para a data
           limite.data AS data_limite,
           m.coletado_em_utc, c.chegada_destino_utc, m.saiu_entrega_utc, m.entregue_em_utc, m.data_entrega_local,
           COALESCE(m.tentativas_falhas, 0) AS tentativas_falhas,
           COALESCE(m.qtd_eventos, 0)       AS qtd_eventos,
           m.ultimo_evento_utc,
           CASE WHEN m.entregue_em_utc IS NOT NULL THEN 'entregue'
                WHEN m.extraviado = 1 THEN 'extraviado'
                WHEN m.devolvido = 1 THEN 'devolvido'
                ELSE 'em_transito' END AS status_atual
    FROM remessa r
    JOIN stg_afetadas a USING (remessa_id)
    JOIN dim_hub ho ON ho.hub_id = r.hub_origem
    JOIN dim_hub hd ON hd.hub_id = r.hub_destino
    JOIN dim_sla s ON s.servico = r.servico AND s.regiao_origem = ho.regiao AND s.regiao_destino = hd.regiao
    JOIN dim_data postagem ON postagem.data = r.data_postagem_local
    JOIN dim_data limite ON limite.seq_dia_util = postagem.seq_dia_util + s.prazo_dias_uteis AND limite.dia_util = 1
    LEFT JOIN marcos m USING (remessa_id)
    LEFT JOIN chegada c USING (remessa_id)
)
SELECT remessa_id, cliente_id, servico, hub_origem, hub_destino, peso_kg, valor_frete, data_postagem_local,
       postado_em_utc, prazo_dias_uteis, data_limite, coletado_em_utc, chegada_destino_utc, saiu_entrega_utc,
       entregue_em_utc, data_entrega_local, tentativas_falhas, qtd_eventos, ultimo_evento_utc, status_atual,
       CASE WHEN status_atual = 'entregue' AND data_entrega_local <= data_limite THEN 'no_prazo'
            WHEN status_atual = 'entregue' THEN 'atrasada'
            WHEN status_atual IN ('extraviado', 'devolvido') THEN 'nao_entregue'
            WHEN :data_lote > data_limite THEN 'em_aberto_atrasada'
            ELSE 'em_aberto_no_prazo' END AS situacao_sla,
       ROUND((julianday(entregue_em_utc) - julianday(postado_em_utc)) * 24, 2) AS lead_time_horas
FROM base;
