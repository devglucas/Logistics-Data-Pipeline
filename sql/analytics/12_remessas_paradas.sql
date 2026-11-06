-- Fila de investigação: remessas em aberto sem evento há 3 dias ou mais no último lote.
WITH corte AS (SELECT MAX(dt) AS data FROM etl_lote)
SELECT f.remessa_id, f.servico, f.hub_origem, f.hub_destino, f.data_limite, f.situacao_sla,
       ultimo.codigo AS ultimo_evento, ultimo.hub_id AS ultimo_hub, date(f.ultimo_evento_utc) AS ultimo_evento_em,
       CAST(julianday(corte.data) - julianday(date(f.ultimo_evento_utc)) AS INTEGER) AS dias_sem_evento
FROM fato_entrega f
CROSS JOIN corte
JOIN fato_evento ultimo ON ultimo.remessa_id = f.remessa_id AND ultimo.ocorrido_em_utc = f.ultimo_evento_utc
WHERE f.status_atual = 'em_transito'
  AND julianday(corte.data) - julianday(date(f.ultimo_evento_utc)) >= 3
ORDER BY dias_sem_evento DESC;
