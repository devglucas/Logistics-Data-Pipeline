SELECT remessa_id, postado_em_utc, entregue_em_utc
FROM fato_entrega
WHERE entregue_em_utc < postado_em_utc;
