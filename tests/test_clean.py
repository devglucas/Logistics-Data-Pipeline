import pandas as pd

from src.clean import data_local, limpar_eventos_parceiro, limpar_eventos_proprios, limpar_remessas, local_para_utc

HUBS = pd.DataFrame({"codigo": ["SAO", "MAO", "RBR"],
                     "fuso": ["America/Sao_Paulo", "America/Manaus", "America/Rio_Branco"]})


def test_mesma_hora_local_em_fusos_diferentes():
    horas = pd.Series(pd.to_datetime(["2025-02-10 22:00", "2025-02-10 22:00", "2025-02-10 22:00"]))
    utc = local_para_utc(horas, pd.Series(HUBS["fuso"].tolist()))
    assert [t.strftime("%d %H:%M") for t in utc] == ["11 01:00", "11 02:00", "11 03:00"]


def test_data_local_difere_da_data_utc():
    utc = pd.Series(pd.to_datetime(["2025-02-11T02:30:00Z"], utc=True))
    assert data_local(utc, pd.Series(["America/Manaus"])).iat[0] == "2025-02-10"


def _proprios(linhas):
    return pd.DataFrame(linhas, columns=["id_evento", "remessa", "codigo", "hub", "ts", "dispositivo"], dtype="string")


def test_eventos_proprios_utc_e_offset_e_quarentena():
    df = _proprios([
        ("E1", "BR1", "RECEBIDO_HUB", "SAO", "2025-02-10T12:00:00Z", "x"),
        ("E2", "BR1", "SAIU_HUB", "SAO", "2025-02-10T09:30:00-03:00", "x"),
        ("E3", "BR1", "SAIU_HUB", "SA0", "2025-02-10T12:00:00Z", "x"),          # hub digitado errado
        ("E4", "BR1", "ENTREGUE", "SAO", "2035-01-01T00:00:00Z", "x"),          # relógio errado
    ])
    validos, rejeitados = limpar_eventos_proprios(df, HUBS, "2025-02-10")
    assert validos["ocorrido_em_utc"].tolist() == ["2025-02-10T12:00:00Z", "2025-02-10T12:30:00Z"]
    assert sorted(rejeitados["motivo"]) == ["hub_desconhecido", "relogio_invalido"]


def test_eventos_parceiro_codigo_hora_local_e_id_estavel():
    df = pd.DataFrame({"awb": [" br2", "BR2"], "status": ["dlv", "DLV"], "base": ["mao", "MAO"],
                       "data_hora": ["10/02/2025 22:00", "10/02/2025 22:00"]}, dtype="string")
    validos, _ = limpar_eventos_parceiro(df, HUBS, "2025-02-11")
    assert validos["codigo"].tolist() == ["ENTREGUE"] * 2
    assert validos["ocorrido_em_utc"].iat[0] == "2025-02-11T02:00:00Z"
    assert validos["data_local"].iat[0] == "2025-02-10"             # entrega foi no dia 10 em Manaus
    assert validos["evento_id"].nunique() == 1                      # reenvio gera o mesmo id


def test_remessas_ultima_versao_e_peso_invalido_nulo():
    df = pd.DataFrame({
        "remessa_id": ["BR1", "BR1", "BR2"], "cliente_id": [" C1 ", "C1", "C2"], "servico": ["Padrão", "STD", "ECO"],
        "hub_origem": ["SAO", "SAO", "SAO"], "hub_destino": ["MAO", "MAO", "RBR"], "cep_destino": ["69000-000", "69000-000", "69900000"],
        "peso_kg": ["1,5", "2.5", "9999"], "valor_frete": ["10.00", "10.00", "20.00"],
        "postado_em": ["2025-02-10 08:00:00"] * 3, "atualizado_em": ["2025-02-10 08:00:00", "2025-02-11 10:00:00", "2025-02-10 08:00:00"],
    }, dtype="string")
    limpas, rejeitados = limpar_remessas(df, HUBS, "2025-02-11")
    limpas = limpas.set_index("remessa_id")
    assert limpas.loc["BR1", "peso_kg"] == 2.5 and limpas.loc["BR1", "servico"] == "padrao"
    assert pd.isna(limpas.loc["BR2", "peso_kg"]) and limpas.loc["BR2", "cep_destino"] == "69900000"
    assert limpas.loc["BR1", "postado_em_utc"] == "2025-02-10T11:00:00Z"
    assert rejeitados.empty
