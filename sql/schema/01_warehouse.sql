-- Warehouse de logística: esquema estrela + controle de carga.
--
--   dim_data, dim_hub, dim_cliente, dim_sla     dimensões
--   remessa                                     cadastro atual de cada remessa (última versão)
--   fato_evento                                 grão: 1 evento de rastreio
--   fato_entrega                                grão: 1 remessa (accumulating snapshot: a linha é
--                                               atualizada a cada novo marco da viagem)
--   stg_*                                       área de trabalho de cada lote
--   etl_lote, quarentena                        controle da carga e registros rejeitados

CREATE TABLE IF NOT EXISTS etl_lote (
    dt              TEXT PRIMARY KEY,
    hash_arquivos   TEXT NOT NULL,
    processado_em   TEXT NOT NULL,
    remessas_lidas  INTEGER NOT NULL,
    eventos_lidos   INTEGER NOT NULL,
    eventos_novos   INTEGER NOT NULL,
    rejeitados      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS quarentena (
    lote_dt  TEXT NOT NULL,
    fonte    TEXT NOT NULL,
    motivo   TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    UNIQUE (lote_dt, fonte, motivo, conteudo)
);

CREATE TABLE IF NOT EXISTS dim_data (
    data         TEXT PRIMARY KEY,          -- AAAA-MM-DD
    ano          INTEGER NOT NULL,
    mes          INTEGER NOT NULL,
    ano_mes      TEXT NOT NULL,
    ano_semana   TEXT NOT NULL,             -- segunda-feira da semana
    dia_semana   INTEGER NOT NULL,          -- 0 = segunda
    dia_util     INTEGER NOT NULL,
    seq_dia_util INTEGER NOT NULL           -- nº do dia útil; em dia não útil, o do próximo dia útil
);

CREATE TABLE IF NOT EXISTS dim_hub (
    hub_id   TEXT PRIMARY KEY,
    cidade   TEXT NOT NULL,
    uf       TEXT NOT NULL,
    regiao   TEXT NOT NULL,
    fuso     TEXT NOT NULL,
    operador TEXT NOT NULL CHECK (operador IN ('propria', 'parceira'))
);

CREATE TABLE IF NOT EXISTS dim_cliente (
    cliente_id TEXT PRIMARY KEY,
    nome       TEXT NOT NULL,
    segmento   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_sla (
    servico          TEXT NOT NULL,
    regiao_origem    TEXT NOT NULL,
    regiao_destino   TEXT NOT NULL,
    prazo_dias_uteis INTEGER NOT NULL CHECK (prazo_dias_uteis > 0),
    PRIMARY KEY (servico, regiao_origem, regiao_destino)
);

CREATE TABLE IF NOT EXISTS remessa (
    remessa_id          TEXT PRIMARY KEY,
    cliente_id          TEXT NOT NULL,
    servico             TEXT NOT NULL,
    hub_origem          TEXT NOT NULL REFERENCES dim_hub (hub_id),
    hub_destino         TEXT NOT NULL REFERENCES dim_hub (hub_id),
    cep_destino         TEXT,
    peso_kg             REAL,
    valor_frete         REAL NOT NULL,
    postado_em_utc      TEXT NOT NULL,
    data_postagem_local TEXT NOT NULL,
    atualizado_em       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fato_evento (
    evento_id       TEXT PRIMARY KEY,       -- id do leitor ou hash do conteúdo (parceira)
    remessa_id      TEXT NOT NULL,
    codigo          TEXT NOT NULL,
    hub_id          TEXT NOT NULL REFERENCES dim_hub (hub_id),
    ocorrido_em_utc TEXT NOT NULL,
    data_local      TEXT NOT NULL,          -- data no fuso do hub onde o evento aconteceu
    fonte           TEXT NOT NULL,
    lote_dt         TEXT NOT NULL           -- em que lote chegou (mede atraso de chegada)
);
CREATE INDEX IF NOT EXISTS ix_evento_remessa ON fato_evento (remessa_id, ocorrido_em_utc);

CREATE TABLE IF NOT EXISTS fato_entrega (
    remessa_id          TEXT PRIMARY KEY,
    cliente_id          TEXT NOT NULL,
    servico             TEXT NOT NULL,
    hub_origem          TEXT NOT NULL,
    hub_destino         TEXT NOT NULL,
    peso_kg             REAL,
    valor_frete         REAL NOT NULL,
    data_postagem_local TEXT NOT NULL,
    postado_em_utc      TEXT NOT NULL,
    prazo_dias_uteis    INTEGER NOT NULL,
    data_limite         TEXT NOT NULL,
    coletado_em_utc     TEXT,
    chegada_destino_utc TEXT,
    saiu_entrega_utc    TEXT,
    entregue_em_utc     TEXT,
    data_entrega_local  TEXT,
    tentativas_falhas   INTEGER NOT NULL,
    qtd_eventos         INTEGER NOT NULL,
    ultimo_evento_utc   TEXT,
    status_atual        TEXT NOT NULL,
    situacao_sla        TEXT NOT NULL,
    lead_time_horas     REAL
);

CREATE TABLE IF NOT EXISTS stg_remessa (
    remessa_id TEXT, cliente_id TEXT, servico TEXT, hub_origem TEXT, hub_destino TEXT, cep_destino TEXT,
    peso_kg REAL, valor_frete REAL, postado_em_utc TEXT, data_postagem_local TEXT, atualizado_em TEXT
);

CREATE TABLE IF NOT EXISTS stg_evento (
    evento_id TEXT, remessa_id TEXT, codigo TEXT, hub_id TEXT, ocorrido_em_utc TEXT, data_local TEXT,
    fonte TEXT, lote_dt TEXT
);

CREATE TABLE IF NOT EXISTS stg_afetadas (remessa_id TEXT PRIMARY KEY);
