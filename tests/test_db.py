import pandas as pd
import pytest

from src.db import comandos_sql, conectar, criar_esquema, inserir


@pytest.fixture
def banco():
    conexao = conectar(":memory:")
    criar_esquema(conexao)
    yield conexao
    conexao.close()


def test_separa_comandos_respeitando_ponto_e_virgula_em_texto():
    script = "-- comentário; com ponto e vírgula\nSELECT 'a;b';\nSELECT 2;\n"
    assert len(comandos_sql(script)) == 2


def test_inserir_converte_nulos(banco):
    df = pd.DataFrame({"hub_id": ["SAO"], "cidade": ["Guarulhos"], "uf": ["SP"], "regiao": ["Sudeste"],
                       "fuso": ["America/Sao_Paulo"], "operador": ["propria"]})
    assert inserir(banco, "dim_hub", df) == 1
    assert banco.execute("SELECT COUNT(*) FROM dim_hub").fetchone()[0] == 1


def test_transacao_desfaz_tudo_se_falhar(banco):
    valido = {"hub_id": ["SAO"], "cidade": ["G"], "uf": ["SP"], "regiao": ["Sudeste"], "fuso": ["X"], "operador": ["propria"]}
    invalido = dict(valido, hub_id=["REC"], operador=["outro"])       # viola o CHECK
    with pytest.raises(Exception):
        with banco:
            inserir(banco, "dim_hub", pd.DataFrame(valido))
            inserir(banco, "dim_hub", pd.DataFrame(invalido))
    assert banco.execute("SELECT COUNT(*) FROM dim_hub").fetchone()[0] == 0
