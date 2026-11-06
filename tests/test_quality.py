import pandas as pd
import pytest

from src.db import conectar, criar_esquema, inserir
from src.load import montar_dim_data
from src.quality import ErroDeQualidade, executar_testes, garantir_qualidade


@pytest.fixture
def banco():
    conexao = conectar(":memory:")
    criar_esquema(conexao)
    inserir(conexao, "dim_data", montar_dim_data())
    return conexao


def _lote(dt):
    return {"dt": dt, "hash_arquivos": "h", "processado_em": "t", "remessas_lidas": 0, "eventos_lidos": 0,
            "eventos_novos": 0, "rejeitados": 0}


def test_banco_vazio_passa(banco):
    resultado = executar_testes(banco)
    assert resultado["passou"].all()
    garantir_qualidade(resultado)


def test_lacuna_de_lotes_interrompe_o_pipeline(banco):
    inserir(banco, "etl_lote", pd.DataFrame([_lote("2025-01-02"), _lote("2025-01-04")]))   # falta o dia 3
    resultado = executar_testes(banco).set_index("teste")
    assert resultado.loc["lacuna_de_lotes", "falhas"] == 1
    with pytest.raises(ErroDeQualidade):
        garantir_qualidade(resultado.reset_index())
