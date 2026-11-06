-- Saiu para entrega há 3 dias ou mais e nada aconteceu: em geral o evento final caiu na quarentena.
SELECT f.remessa_id, f.hub_destino, date(f.ultimo_evento_utc) AS ultimo_evento
FROM fato_entrega f
WHERE f.status_atual = 'em_transito' AND f.saiu_entrega_utc IS NOT NULL
  AND julianday((SELECT MAX(dt) FROM etl_lote)) - julianday(date(f.ultimo_evento_utc)) >= 3;
