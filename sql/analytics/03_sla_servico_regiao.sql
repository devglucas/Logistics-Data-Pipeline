-- OTD por serviço e região de destino.
SELECT f.servico, h.regiao AS regiao_destino,
       COUNT(*)                                                 AS entregues,
       ROUND(100.0 * SUM(f.situacao_sla = 'no_prazo') / COUNT(*), 2) AS otd_pct,
       ROUND(AVG(f.lead_time_horas) / 24, 2)                    AS lead_time_medio_dias,
       ROUND(AVG(f.prazo_dias_uteis), 1)                        AS prazo_medio_dias_uteis
FROM fato_entrega f
JOIN dim_hub h ON h.hub_id = f.hub_destino
WHERE f.status_atual = 'entregue'
GROUP BY f.servico, h.regiao
ORDER BY f.servico, otd_pct;
