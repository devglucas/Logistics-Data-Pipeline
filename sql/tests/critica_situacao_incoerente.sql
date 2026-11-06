SELECT remessa_id, status_atual, situacao_sla
FROM fato_entrega
WHERE (status_atual = 'entregue') <> (situacao_sla IN ('no_prazo', 'atrasada'))
   OR (status_atual = 'entregue' AND (data_entrega_local IS NULL OR lead_time_horas IS NULL))
   OR (status_atual = 'em_transito' AND situacao_sla NOT LIKE 'em_aberto%');
