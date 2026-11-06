-- OTD (on-time delivery) por mês da data limite, com variação sobre o mês anterior (LAG).
-- Só entram prazos JÁ VENCIDOS no corte, e o que segue em aberto depois do prazo conta como
-- atraso. Sem isso, o mês mais recente parece perfeito: as únicas entregas registradas nele
-- são as rápidas, e as que vão atrasar ainda não aparecem (viés de sobrevivência).
WITH mensal AS (
    SELECT d.ano_mes,
           COUNT(*)                       AS prazos_vencidos,
           SUM(situacao_sla = 'no_prazo') AS no_prazo,
           SUM(situacao_sla = 'atrasada') AS atrasadas,
           SUM(situacao_sla = 'em_aberto_atrasada') AS em_aberto_atrasadas
    FROM fato_entrega f
    JOIN dim_data d ON d.data = f.data_limite
    WHERE f.situacao_sla IN ('no_prazo', 'atrasada', 'em_aberto_atrasada')
      AND f.data_limite <= (SELECT MAX(dt) FROM etl_lote)
    GROUP BY d.ano_mes
)
SELECT ano_mes, prazos_vencidos, no_prazo, atrasadas, em_aberto_atrasadas,
       ROUND(100.0 * no_prazo / prazos_vencidos, 2) AS otd_pct,
       ROUND(100.0 * no_prazo / prazos_vencidos
             - LAG(100.0 * no_prazo / prazos_vencidos) OVER (ORDER BY ano_mes), 2) AS variacao_pp
FROM mensal
ORDER BY ano_mes;
