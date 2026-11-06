-- Toda remessa precisa ter sua linha na fato de entrega (falharia, por exemplo, sem prazo em dim_sla).
SELECT r.remessa_id
FROM remessa r
LEFT JOIN fato_entrega f USING (remessa_id)
WHERE f.remessa_id IS NULL;
