-- Em quantos dias o evento chega ao warehouse depois de acontecer, por fonte.
SELECT fonte,
       CAST(julianday(lote_dt) - julianday(data_local) AS INTEGER) AS dias_de_atraso,
       COUNT(*) AS eventos,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY fonte), 2) AS pct_da_fonte
FROM fato_evento
GROUP BY fonte, dias_de_atraso
ORDER BY fonte, dias_de_atraso;
