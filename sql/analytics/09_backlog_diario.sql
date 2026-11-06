-- Remessas em aberto no fim de cada dia: postadas até o dia e ainda não encerradas.
-- O encerramento é a entrega ou o último evento de extravio/devolução.
WITH encerramento AS (
    SELECT remessa_id, data_postagem_local,
           CASE WHEN status_atual = 'entregue' THEN data_entrega_local
                WHEN status_atual IN ('extraviado', 'devolvido') THEN date(ultimo_evento_utc) END AS encerrada_em
    FROM fato_entrega
)
SELECT d.data, d.dia_util,
       COUNT(*)                               AS em_aberto
FROM dim_data d
JOIN encerramento e ON e.data_postagem_local <= d.data AND (e.encerrada_em IS NULL OR e.encerrada_em > d.data)
WHERE d.data BETWEEN (SELECT MIN(dt) FROM etl_lote) AND (SELECT MAX(dt) FROM etl_lote)
GROUP BY d.data
ORDER BY d.data;
