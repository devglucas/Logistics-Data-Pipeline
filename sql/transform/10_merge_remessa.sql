-- Upsert das remessas do lote. A remessa pode chegar reenviada (peso corrigido) e até fora de
-- ordem: só uma versão igual ou mais nova substitui a atual.
INSERT INTO remessa
SELECT remessa_id, cliente_id, servico, hub_origem, hub_destino, cep_destino, peso_kg, valor_frete,
       postado_em_utc, data_postagem_local, atualizado_em
FROM stg_remessa
WHERE true
ON CONFLICT (remessa_id) DO UPDATE SET
    cliente_id    = excluded.cliente_id,
    servico       = excluded.servico,
    hub_destino   = excluded.hub_destino,
    cep_destino   = excluded.cep_destino,
    peso_kg       = excluded.peso_kg,
    valor_frete   = excluded.valor_frete,
    atualizado_em = excluded.atualizado_em
WHERE excluded.atualizado_em >= remessa.atualizado_em;
