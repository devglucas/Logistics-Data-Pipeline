-- Volume e OTD por semana, com média móvel de 4 semanas e acumulado (molduras de janela).
WITH semanal AS (
    SELECT d.ano_semana,
           COUNT(*)                                                       AS entregues,
           100.0 * SUM(f.situacao_sla = 'no_prazo') / COUNT(*)            AS otd_pct
    FROM fato_entrega f
    JOIN dim_data d ON d.data = f.data_entrega_local
    WHERE f.status_atual = 'entregue'
    GROUP BY d.ano_semana
)
SELECT ano_semana, entregues, ROUND(otd_pct, 2) AS otd_pct,
       ROUND(AVG(otd_pct) OVER (ORDER BY ano_semana ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 2) AS otd_media_4_semanas,
       SUM(entregues) OVER (ORDER BY ano_semana ROWS UNBOUNDED PRECEDING)                         AS entregues_acumulado
FROM semanal
ORDER BY ano_semana;
