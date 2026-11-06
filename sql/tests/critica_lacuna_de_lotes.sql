-- Dias sem lote processado entre o primeiro e o último: a carga pulou uma partição.
SELECT d.data
FROM dim_data d
LEFT JOIN etl_lote l ON l.dt = d.data
WHERE d.data BETWEEN (SELECT MIN(dt) FROM etl_lote) AND (SELECT MAX(dt) FROM etl_lote)
  AND l.dt IS NULL;
