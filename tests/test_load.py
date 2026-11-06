"""Propriedades da carga incremental, sobre os lotes reais de data/raw."""

import pandas as pd
import pytest

from src import load
from src.db import conectar, consultar, criar_esquema
from src.extract import lotes_pendentes
from src.load import carregar_dimensoes, montar_dim_data, processar_lote

COLUNAS = ["remessa_id", "status_atual", "peso_kg", "data_limite", "entregue_em_utc", "data_entrega_local",
           "tentativas_falhas", "qtd_eventos", "lead_time_horas"]


def banco_novo():
    conexao = conectar(":memory:")
    criar_esquema(conexao)
    return conexao, carregar_dimensoes(conexao)


def snapshot(conexao) -> pd.DataFrame:
    return consultar(conexao, f"SELECT {', '.join(COLUNAS)} FROM fato_entrega ORDER BY remessa_id")


@pytest.fixture(scope="module")
def carga_completa():
    conexao, hubs = banco_novo()
    for lote in lotes_pendentes(conexao):
        processar_lote(conexao, *lote, hubs)
    return conexao, hubs


def test_segunda_execucao_nao_tem_o_que_fazer(carga_completa):
    conexao, _ = carga_completa
    assert lotes_pendentes(conexao) == []


def test_carga_em_duas_etapas_igual_a_carga_unica(carga_completa):
    conexao, hubs = banco_novo()
    for lote in lotes_pendentes(conexao, ate="2025-02-15"):
        processar_lote(conexao, *lote, hubs)
    assert conexao.execute("SELECT MAX(dt) FROM etl_lote").fetchone()[0] == "2025-02-15"
    for lote in lotes_pendentes(conexao):
        processar_lote(conexao, *lote, hubs)
    pd.testing.assert_frame_equal(snapshot(conexao), snapshot(carga_completa[0]))


def test_ordem_dos_lotes_nao_muda_o_resultado(carga_completa):
    conexao, hubs = banco_novo()
    for lote in reversed(lotes_pendentes(conexao)):
        processar_lote(conexao, *lote, hubs)
    pd.testing.assert_frame_equal(snapshot(conexao), snapshot(carga_completa[0]))


def test_reprocessar_um_lote_e_idempotente(carga_completa):
    conexao, hubs = carga_completa
    antes = snapshot(conexao)
    eventos = conexao.execute("SELECT COUNT(*) FROM fato_evento").fetchone()[0]
    with conexao:
        conexao.execute("UPDATE etl_lote SET hash_arquivos = 'mudou' WHERE dt = '2025-02-11'")
    pendentes = lotes_pendentes(conexao)
    assert [p[0] for p in pendentes] == ["2025-02-11"]
    processar_lote(conexao, *pendentes[0], hubs)
    assert conexao.execute("SELECT COUNT(*) FROM fato_evento").fetchone()[0] == eventos
    pd.testing.assert_frame_equal(snapshot(conexao), antes)


def test_lote_com_falha_nao_deixa_nada_no_banco(tmp_path, monkeypatch):
    conexao, hubs = banco_novo()
    lote = lotes_pendentes(conexao)[0]
    ruim = tmp_path / "99_quebra.sql"
    ruim.write_text("SELECT coluna_que_nao_existe FROM fato_evento;\n", encoding="utf-8")
    monkeypatch.setattr(load, "TRANSFORMACOES", [*load.TRANSFORMACOES, ruim])
    with pytest.raises(Exception):
        processar_lote(conexao, *lote, hubs)
    for tabela in ["fato_evento", "remessa", "fato_entrega", "etl_lote"]:
        assert conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0] == 0, tabela


def test_sequencia_de_dias_uteis():
    dias = montar_dim_data().set_index("data")
    sexta, sabado, segunda = dias.loc["2025-02-07"], dias.loc["2025-02-08"], dias.loc["2025-02-10"]
    assert sabado["dia_util"] == 0 and sabado["seq_dia_util"] == segunda["seq_dia_util"]
    assert segunda["seq_dia_util"] == sexta["seq_dia_util"] + 1
    # carnaval: sexta 28/02 -> quarta 05/03 é o dia útil seguinte
    assert dias.loc["2025-03-05", "seq_dia_util"] == dias.loc["2025-02-28", "seq_dia_util"] + 1
