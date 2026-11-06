-- Ranking dos hubs de destino pelo OTD, com a posição dentro do tipo de operador.
WITH por_hub AS (
    SELECT f.hub_destino, h.cidade, h.regiao, h.operador,
           COUNT(*)                                                  AS entregues,
           ROUND(100.0 * SUM(f.situacao_sla = 'no_prazo') / COUNT(*), 2) AS otd_pct,
           ROUND(100.0 * SUM(f.tentativas_falhas > 0) / COUNT(*), 2) AS pct_tentativa_falha
    FROM fato_entrega f
    JOIN dim_hub h ON h.hub_id = f.hub_destino
    WHERE f.status_atual = 'entregue'
    GROUP BY f.hub_destino
)
SELECT *,
       DENSE_RANK() OVER (ORDER BY otd_pct)                       AS pior_otd_geral,
       DENSE_RANK() OVER (PARTITION BY operador ORDER BY otd_pct) AS pior_otd_no_operador
FROM por_hub
ORDER BY otd_pct;
