-- Eventos cuja remessa ainda não chegou. Normal entre lotes; no fim, indica remessa perdida na fonte.
SELECT e.remessa_id, e.evento_id
FROM fato_evento e
LEFT JOIN remessa r USING (remessa_id)
WHERE r.remessa_id IS NULL;
