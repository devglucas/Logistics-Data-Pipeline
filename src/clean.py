"""
Limpeza de cada lote.

O ponto central é o tempo. Cada sistema grava de um jeito:
- leitores próprios: ISO 8601 com fuso (Z ou -03:00)
- parceira: hora local da base, sem fuso ('07/02/2025 08:13')
- sistema comercial: hora local do hub de origem, sem fuso

Tudo vira UTC, para que a ordem dos eventos seja a real, mesmo entre hubs em
fusos diferentes. Além disso guardamos a data LOCAL do evento: uma entrega às
22h em Manaus já é o dia seguinte em UTC, e o prazo vale pela data local.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata

import pandas as pd

from src.config import DIAS_MAXIMOS_ATRASO_EVENTO, PESO_MAXIMO_KG

CODIGOS_VALIDOS = {"POSTADO", "COLETADO", "RECEBIDO_HUB", "SAIU_HUB", "SAIU_ENTREGA", "TENTATIVA_FALHA", "ENTREGUE",
                   "EXTRAVIADO", "DEVOLVIDO"}
CODIGOS_PARCEIRO = {"POS": "POSTADO", "COL": "COLETADO", "REC": "RECEBIDO_HUB", "EXP": "SAIU_HUB", "OUT": "SAIU_ENTREGA",
                    "NOK": "TENTATIVA_FALHA", "DLV": "ENTREGUE", "LOST": "EXTRAVIADO", "RTN": "DEVOLVIDO"}
SERVICOS = {"expresso": "expresso", "exp": "expresso", "padrao": "padrao", "std": "padrao",
            "economico": "economico", "eco": "economico"}
FORMATO_UTC = "%Y-%m-%dT%H:%M:%SZ"


def _sem_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def _para_quarentena(df: pd.DataFrame, fonte: str, motivo: str, lote_dt: str) -> pd.DataFrame:
    conteudo = [json.dumps({k: (None if pd.isna(v) else str(v)) for k, v in linha.items()}, ensure_ascii=False)
                for linha in df.to_dict("records")]
    return pd.DataFrame({"lote_dt": lote_dt, "fonte": fonte, "motivo": motivo, "conteudo": conteudo})


def local_para_utc(horas_locais: pd.Series, fusos: pd.Series) -> pd.Series:
    """Hora local sem fuso -> UTC, cada linha no fuso do seu hub."""
    resultado = pd.Series(pd.NaT, index=horas_locais.index, dtype="datetime64[us, UTC]")
    for fuso, indice in horas_locais.groupby(fusos).groups.items():
        resultado.loc[indice] = horas_locais.loc[indice].dt.tz_localize(fuso).dt.tz_convert("UTC")
    return resultado


def data_local(horas_utc: pd.Series, fusos: pd.Series) -> pd.Series:
    """Data no fuso de cada hub."""
    resultado = pd.Series(pd.NA, index=horas_utc.index, dtype="string")
    for fuso, indice in horas_utc.groupby(fusos).groups.items():
        resultado.loc[indice] = horas_utc.loc[indice].dt.tz_convert(fuso).dt.strftime("%Y-%m-%d")
    return resultado


def _validar_eventos(df: pd.DataFrame, hubs: pd.DataFrame, fonte: str, lote_dt: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """df traz remessa_id, codigo, hub_id e ocorrido (UTC). Separa o que vai para a quarentena."""
    lote = pd.Timestamp(lote_dt, tz="UTC")
    regras = [
        (~df["hub_id"].isin(hubs["codigo"]), "hub_desconhecido"),
        (~df["codigo"].isin(CODIGOS_VALIDOS), "codigo_desconhecido"),
        (df["ocorrido"].isna() | (df["ocorrido"] > lote + pd.Timedelta(days=2))
         | (df["ocorrido"] < lote - pd.Timedelta(days=DIAS_MAXIMOS_ATRASO_EVENTO)), "relogio_invalido"),
    ]
    rejeitados = []
    for invalido, motivo in regras:
        invalido = invalido.reindex(df.index).fillna(False).astype(bool)
        if invalido.any():
            rejeitados.append(_para_quarentena(df.loc[invalido].drop(columns="ocorrido"), fonte, motivo, lote_dt))
        df = df.loc[~invalido]
    fusos = df["hub_id"].map(hubs.set_index("codigo")["fuso"])
    validos = df.assign(
        ocorrido_em_utc=df["ocorrido"].dt.strftime(FORMATO_UTC),
        data_local=data_local(df["ocorrido"], fusos),
        fonte=fonte, lote_dt=lote_dt,
    )
    colunas = ["evento_id", "remessa_id", "codigo", "hub_id", "ocorrido_em_utc", "data_local", "fonte", "lote_dt"]
    return validos[colunas], pd.concat(rejeitados) if rejeitados else pd.DataFrame()


def limpar_eventos_proprios(df: pd.DataFrame, hubs: pd.DataFrame, lote_dt: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    eventos = df.assign(
        evento_id=df["id_evento"], remessa_id=df["remessa"].str.strip().str.upper(), hub_id=df["hub"].str.strip().str.upper(),
        codigo=df["codigo"].str.strip().str.upper(),
        ocorrido=pd.to_datetime(df["ts"], utc=True, format="ISO8601", errors="coerce"),
    )[["evento_id", "remessa_id", "codigo", "hub_id", "ocorrido"]]
    return _validar_eventos(eventos, hubs, "proprio", lote_dt)


def limpar_eventos_parceiro(df: pd.DataFrame, hubs: pd.DataFrame, lote_dt: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    hub = df["base"].str.strip().str.upper()
    fusos = hub.map(hubs.set_index("codigo")["fuso"]).fillna("UTC")
    hora_local = pd.to_datetime(df["data_hora"], format="%d/%m/%Y %H:%M", errors="coerce")
    eventos = df.assign(
        remessa_id=df["awb"].str.strip().str.upper(), hub_id=hub,
        codigo=df["status"].str.strip().str.upper().map(CODIGOS_PARCEIRO),
        ocorrido=local_para_utc(hora_local, fusos),
    )
    # a parceira não manda id: o hash do conteúdo identifica o evento e torna o reenvio idempotente
    chave = eventos["remessa_id"] + "|" + eventos["codigo"].fillna("?") + "|" + eventos["hub_id"] + "|" + df["data_hora"]
    eventos["evento_id"] = chave.map(lambda c: "P" + hashlib.sha1(c.encode()).hexdigest()[:16])
    return _validar_eventos(eventos[["evento_id", "remessa_id", "codigo", "hub_id", "ocorrido"]], hubs, "parceiro", lote_dt)


def limpar_remessas(df: pd.DataFrame, hubs: pd.DataFrame, lote_dt: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    peso = pd.to_numeric(df["peso_kg"].str.replace(",", ".", regex=False), errors="coerce")
    postado_local = pd.to_datetime(df["postado_em"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    limpas = df.assign(
        remessa_id=df["remessa_id"].str.strip().str.upper(),
        cliente_id=df["cliente_id"].str.strip(),
        servico=df["servico"].str.strip().str.lower().map(lambda s: SERVICOS.get(_sem_acentos(s)) if pd.notna(s) else None),
        cep_destino=df["cep_destino"].str.replace(r"\D", "", regex=True),
        peso_kg=peso.where(peso.gt(0) & peso.le(PESO_MAXIMO_KG)),  # peso inválido vira nulo: a remessa continua válida
        valor_frete=pd.to_numeric(df["valor_frete"], errors="coerce"),
    )
    invalido = (limpas["servico"].isna() | ~limpas["hub_origem"].isin(hubs["codigo"]) | ~limpas["hub_destino"].isin(hubs["codigo"])
                | postado_local.isna() | limpas["valor_frete"].isna())
    rejeitados = _para_quarentena(df.loc[invalido], "remessas", "remessa_invalida", lote_dt) if invalido.any() else pd.DataFrame()
    limpas, postado_local = limpas.loc[~invalido], postado_local.loc[~invalido]

    fusos = limpas["hub_origem"].map(hubs.set_index("codigo")["fuso"])
    limpas = limpas.assign(
        postado_em_utc=local_para_utc(postado_local, fusos).dt.strftime(FORMATO_UTC),
        data_postagem_local=postado_local.dt.strftime("%Y-%m-%d"),
    )
    # a mesma remessa pode vir duas vezes no lote: vale a última atualização
    limpas = limpas.sort_values("atualizado_em").drop_duplicates("remessa_id", keep="last")
    colunas = ["remessa_id", "cliente_id", "servico", "hub_origem", "hub_destino", "cep_destino", "peso_kg", "valor_frete",
               "postado_em_utc", "data_postagem_local", "atualizado_em"]
    return limpas[colunas], rejeitados
