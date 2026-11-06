-- Clientes com pior OTD entre os que têm volume relevante.
WITH por_cliente AS (
    SELECT f.cliente_id, c.nome, c.segmento, COUNT(*) AS entregues,
           ROUND(100.0 * SUM(f.situacao_sla = 'no_prazo') / COUNT(*), 2) AS otd_pct,
           ROUND(SUM(f.valor_frete), 2) AS frete
    FROM fato_entrega f
    JOIN dim_cliente c USING (cliente_id)
    WHERE f.status_atual = 'entregue'
    GROUP BY f.cliente_id
    HAVING COUNT(*) >= 30
)
SELECT *, DENSE_RANK() OVER (ORDER BY otd_pct) AS ranking
FROM por_cliente
ORDER BY otd_pct
LIMIT 15;
