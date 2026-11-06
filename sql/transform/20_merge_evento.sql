-- Eventos entram uma única vez: o reenvio do mesmo evento em outro lote é ignorado pela chave.
INSERT OR IGNORE INTO fato_evento
SELECT evento_id, remessa_id, codigo, hub_id, ocorrido_em_utc, data_local, fonte, lote_dt
FROM stg_evento;
