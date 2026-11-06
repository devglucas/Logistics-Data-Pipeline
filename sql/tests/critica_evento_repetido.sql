-- O mesmo fato físico não pode entrar duas vezes com ids diferentes.
SELECT remessa_id, codigo, hub_id, ocorrido_em_utc, COUNT(*) AS vezes
FROM fato_evento
GROUP BY remessa_id, codigo, hub_id, ocorrido_em_utc
HAVING COUNT(*) > 1;
