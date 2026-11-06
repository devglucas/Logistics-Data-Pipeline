-- Remessa em aberto vence o prazo sem que nenhum evento chegue: o tempo passar também muda a situação.
UPDATE fato_entrega
SET situacao_sla = 'em_aberto_atrasada'
WHERE situacao_sla = 'em_aberto_no_prazo' AND :data_lote > data_limite;
