SELECT e.remessa_id, e.codigo, e.ocorrido_em_utc, f.entregue_em_utc
FROM fato_evento e
JOIN fato_entrega f USING (remessa_id)
WHERE f.entregue_em_utc IS NOT NULL AND e.ocorrido_em_utc > f.entregue_em_utc;
