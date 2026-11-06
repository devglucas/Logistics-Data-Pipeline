-- Lead time por serviço e par de regiões. SQLite não tem PERCENTILE_CONT: os percentis saem
-- da posição de cada remessa na ordem do grupo (ROW_NUMBER sobre COUNT).
WITH ordenado AS (
    SELECT f.servico, ho.regiao AS regiao_origem, hd.regiao AS regiao_destino,
           f.lead_time_horas / 24.0 AS dias,
           ROW_NUMBER() OVER grupo_ordenado AS posicao,
           COUNT(*) OVER grupo             AS total
    FROM fato_entrega f
    JOIN dim_hub ho ON ho.hub_id = f.hub_origem
    JOIN dim_hub hd ON hd.hub_id = f.hub_destino
    WHERE f.status_atual = 'entregue'
    WINDOW grupo AS (PARTITION BY f.servico, ho.regiao, hd.regiao),
           grupo_ordenado AS (PARTITION BY f.servico, ho.regiao, hd.regiao ORDER BY f.lead_time_horas)
)
SELECT servico, regiao_origem, regiao_destino, MAX(total) AS entregues,
       ROUND(AVG(dias), 2)                                                     AS media_dias,
       ROUND(MIN(CASE WHEN posicao >= 0.5 * total THEN dias END), 2)           AS p50_dias,
       ROUND(MIN(CASE WHEN posicao >= 0.9 * total THEN dias END), 2)           AS p90_dias
FROM ordenado
GROUP BY servico, regiao_origem, regiao_destino
HAVING MAX(total) >= 20
ORDER BY p90_dias DESC;
