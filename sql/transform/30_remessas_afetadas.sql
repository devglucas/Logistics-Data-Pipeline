-- Carga incremental: só recalcula as remessas tocadas por este lote. Inclui os eventos atrasados
-- (reabrem remessas antigas) e as remessas que chegaram depois dos seus eventos.
DELETE FROM stg_afetadas;

INSERT OR IGNORE INTO stg_afetadas
SELECT remessa_id FROM stg_remessa
UNION
SELECT remessa_id FROM stg_evento;
