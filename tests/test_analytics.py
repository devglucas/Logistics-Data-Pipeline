"""Consultas analíticas sobre um banco pequeno, com casos construídos à mão."""

import pandas as pd
import pytest

from src.config import SQL_DIR
from src.db import conectar, consultar, criar_esquema, inserir
from src.load import montar_dim_data


@pytest.fixture
def banco():
    conexao = conectar(":memory:")
    criar_esquema(conexao)
    inserir(conexao, "dim_data", montar_dim_data())
    inserir(conexao, "dim_hub", pd.DataFrame({"hub_id": ["SAO", "REC"], "cidade": ["G", "R"], "uf": ["SP", "PE"],
                                              "regiao": ["Sudeste", "Nordeste"], "fuso": ["x", "y"],
                                              "operador": ["propria", "parceira"]}))
    inserir(conexao, "etl_lote", pd.DataFrame({"dt": ["2025-03-20"], "hash_arquivos": ["h"], "processado_em": ["t"],
                                               "remessas_lidas": [0], "eventos_lidos": [0], "eventos_novos": [0], "rejeitados": [0]}))
    return conexao


def _sql(nome: str) -> str:
    return (SQL_DIR / "analytics" / nome).read_text(encoding="utf-8")


def _entrega(remessa, limite, situacao, status="entregue"):
    return {"remessa_id": remessa, "cliente_id": "C", "servico": "padrao", "hub_origem": "SAO", "hub_destino": "REC",
            "valor_frete": 10.0, "data_postagem_local": "2025-02-03", "postado_em_utc": "2025-02-03T12:00:00Z",
            "prazo_dias_uteis": 3, "data_limite": limite, "tentativas_falhas": 0, "qtd_eventos": 1,
            "status_atual": status, "situacao_sla": situacao}


def test_otd_mensal_ignora_prazos_ainda_nao_vencidos(banco):
    inserir(banco, "fato_entrega", pd.DataFrame([
        _entrega("A", "2025-03-10", "no_prazo"),
        _entrega("B", "2025-03-11", "em_aberto_atrasada", "em_transito"),   # conta como atraso
        _entrega("C", "2025-03-25", "no_prazo"),                            # prazo ainda não venceu
        _entrega("D", "2025-03-12", "nao_entregue", "extraviado"),          # não entra no OTD
    ]))
    linha = consultar(banco, _sql("02_sla_mensal.sql")).iloc[0]
    assert linha["prazos_vencidos"] == 2 and linha["otd_pct"] == 50.0


def test_permanencia_mede_ate_o_proximo_evento_no_mesmo_hub(banco):
    eventos = [("1", "BR", "RECEBIDO_HUB", "SAO", "2025-02-03T10:00:00Z"), ("3", "BR", "SAIU_HUB", "SAO", "2025-02-03T16:00:00Z"),
               ("2", "BR", "RECEBIDO_HUB", "REC", "2025-02-05T10:00:00Z"), ("4", "BR", "SAIU_ENTREGA", "REC", "2025-02-06T10:00:00Z")]
    df = pd.DataFrame(eventos, columns=["evento_id", "remessa_id", "codigo", "hub_id", "ocorrido_em_utc"])
    inserir(banco, "fato_evento", df.assign(data_local="2025-02-03", fonte="p", lote_dt="2025-02-03"))
    resultado = consultar(banco, _sql("06_permanencia_hub.sql")).set_index("hub_id")
    assert resultado.loc["SAO", "horas_medias"] == 6.0 and resultado.loc["REC", "horas_medias"] == 24.0
    assert resultado.loc["REC", "ranking_gargalo"] == 1
