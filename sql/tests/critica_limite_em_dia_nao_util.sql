SELECT f.remessa_id, f.data_limite
FROM fato_entrega f
JOIN dim_data d ON d.data = f.data_limite
WHERE d.dia_util = 0;
