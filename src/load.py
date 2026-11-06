"""
Carga incremental no warehouse.

Cada lote roda em UMA transação: staging -> merges -> recálculo das remessas afetadas ->
registro em etl_lote. Se qualquer passo falhar, nada do lote fica no banco e ele
continua pendente para a próxima execução.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.clean import limpar_eventos_parceiro, limpar_eventos_proprios, limpar_remessas
from src.config import CALENDARIO_FIM, CALENDARIO_INICIO, FERIADOS, SQL_DIR
from src.db import executar_arquivo, inserir
from src.extract import ler_lote, ler_referencias
from src.utils import configurar_logger

log = configurar_logger("load")

TRANSFORMACOES = sorted((SQL_DIR / "transform").glob("*.sql"))


def montar_dim_data() -> pd.DataFrame:
    datas = pd.date_range(CALENDARIO_INICIO, CALENDARIO_FIM, freq="D")
    util = np.is_busday(datas.values.astype("datetime64[D]"), holidays=FERIADOS.values.astype("datetime64[D]"))
    sequencia = pd.Series(util.astype(int)).cumsum()
    # dia não útil herda a sequência do PRÓXIMO dia útil: postar no sábado conta a partir de segunda
    sequencia = sequencia.where(util, sequencia + 1)
    return pd.DataFrame({
        "data": datas.strftime("%Y-%m-%d"), "ano": datas.year, "mes": datas.month, "ano_mes": datas.strftime("%Y-%m"),
        "ano_semana": (datas - pd.to_timedelta(datas.dayofweek, unit="D")).strftime("%Y-%m-%d"),
        "dia_semana": datas.dayofweek, "dia_util": util.astype(int), "seq_dia_util": sequencia.values,
    })


def carregar_dimensoes(conexao: sqlite3.Connection) -> pd.DataFrame:
    referencias = ler_referencias()
    with conexao:
        inserir(conexao, "dim_data", montar_dim_data(), "INSERT OR REPLACE")
        inserir(conexao, "dim_hub", referencias["hubs"].rename(columns={"codigo": "hub_id"}), "INSERT OR REPLACE")
        inserir(conexao, "dim_cliente", referencias["clientes"], "INSERT OR REPLACE")
        inserir(conexao, "dim_sla", referencias["sla_servico"], "INSERT OR REPLACE")
    return referencias["hubs"]


def processar_lote(conexao: sqlite3.Connection, dt: str, pasta, hash_lote: str, hubs: pd.DataFrame) -> dict:
    dados = ler_lote(pasta)
    remessas, rej_remessas = limpar_remessas(dados["remessas"], hubs, dt)
    proprios, rej_proprios = limpar_eventos_proprios(dados["proprios"], hubs, dt)
    parceiro, rej_parceiro = limpar_eventos_parceiro(dados["parceiro"], hubs, dt)
    eventos = pd.concat([proprios, parceiro], ignore_index=True)
    rejeitados = pd.concat([rej_remessas, rej_proprios, rej_parceiro], ignore_index=True)

    with conexao:  # uma transação por lote
        conexao.execute("DELETE FROM stg_remessa")
        conexao.execute("DELETE FROM stg_evento")
        inserir(conexao, "stg_remessa", remessas)
        inserir(conexao, "stg_evento", eventos)
        inserir(conexao, "quarentena", rejeitados, "INSERT OR IGNORE")
        antes = conexao.execute("SELECT COUNT(*) FROM fato_evento").fetchone()[0]
        for arquivo in TRANSFORMACOES:
            executar_arquivo(conexao, arquivo, {"data_lote": dt})
        novos = conexao.execute("SELECT COUNT(*) FROM fato_evento").fetchone()[0] - antes
        resumo = {"dt": dt, "hash_arquivos": hash_lote, "processado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "remessas_lidas": len(remessas), "eventos_lidos": len(eventos), "eventos_novos": novos,
                  "rejeitados": len(rejeitados)}
        inserir(conexao, "etl_lote", pd.DataFrame([resumo]), "INSERT OR REPLACE")
    return resumo
