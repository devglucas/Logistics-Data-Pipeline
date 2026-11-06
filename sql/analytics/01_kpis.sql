-- Indicadores gerais do período. OTD considera só prazos já vencidos no corte.
WITH corte AS (SELECT MAX(dt) AS data FROM etl_lote),
vencidas AS (
    SELECT f.* FROM fato_entrega f, corte
    WHERE f.data_limite <= corte.data AND f.situacao_sla IN ('no_prazo', 'atrasada', 'em_aberto_atrasada')
)
SELECT (SELECT COUNT(*) FROM fato_entrega)                                          AS remessas,
       (SELECT SUM(status_atual = 'entregue') FROM fato_entrega)                    AS entregues,
       COUNT(*)                                                                     AS prazos_vencidos,
       SUM(situacao_sla = 'no_prazo')                                               AS no_prazo,
       ROUND(100.0 * SUM(situacao_sla = 'no_prazo') / COUNT(*), 2)                  AS otd_pct,
       (SELECT SUM(status_atual = 'em_transito') FROM fato_entrega)                 AS em_transito,
       SUM(situacao_sla = 'em_aberto_atrasada')                                     AS em_aberto_atrasadas,
       (SELECT SUM(status_atual = 'extraviado') FROM fato_entrega)                  AS extraviadas,
       (SELECT SUM(status_atual = 'devolvido') FROM fato_entrega)                   AS devolvidas,
       (SELECT ROUND(AVG(lead_time_horas) / 24, 2) FROM fato_entrega)               AS lead_time_medio_dias,
       (SELECT ROUND(100.0 * SUM(tentativas_falhas > 0) / COUNT(*), 2) FROM fato_entrega) AS pct_com_tentativa_falha,
       (SELECT ROUND(SUM(valor_frete), 2) FROM fato_entrega)                        AS frete_total
FROM vencidas;
