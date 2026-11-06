"""Compara o warehouse com o gabarito e separa os motivos de cada divergência."""

from __future__ import annotations

import json
import sqlite3

import pandas as pd

from src.config import EXTERNAL_DIR
from src.db import consultar
from src.utils import configurar_logger

log = configurar_logger("evaluate")


def avaliar(conexao: sqlite3.Connection) -> pd.DataFrame | None:
    caminho = EXTERNAL_DIR / "gabarito_entregas.csv"
    if not caminho.exists():
        return None
    gabarito = pd.read_csv(caminho, dtype="string")
    fato = consultar(conexao, "SELECT remessa_id, status_atual, data_limite, data_entrega_local, situacao_sla FROM fato_entrega")
    m = gabarito.merge(fato, on="remessa_id", how="left", suffixes=("_real", ""))

    entregues = m[m["status_atual"].eq("entregue") & m["status_final"].eq("entregue")]
    prazo_real = entregues["no_prazo"].str.lower().eq("true")
    divergentes = m[m["status_atual"] != m["status_final"]]

    # por que o warehouse não sabe do desfecho? o evento final está na quarentena ou ainda não chegou
    quarentena = consultar(conexao, "SELECT conteudo FROM quarentena WHERE fonte <> 'remessas'")["conteudo"].map(json.loads)
    finais = {q["remessa_id"] for q in quarentena if q.get("codigo") in ("ENTREGUE", "EXTRAVIADO", "DEVOLVIDO")}
    em_quarentena = divergentes["remessa_id"].isin(finais)

    resultado = pd.DataFrame([
        ("Remessas no gabarito", len(gabarito)),
        ("Remessas no warehouse", int(m["status_atual"].notna().sum())),
        ("Data limite correta", int((m["data_limite"] == m["data_limite_real"]).sum())),
        ("Status igual ao real", int((m["status_atual"] == m["status_final"]).sum())),
        ("Status divergente: evento final em quarentena", int(em_quarentena.sum())),
        ("Status divergente: evento final ainda não chegou no corte", int((~em_quarentena).sum())),
        ("Entregas com data local correta", int((entregues["data_entrega_local"] == entregues["data_entrega_local_real"]).sum())),
        ("Entregas conferidas", len(entregues)),
        ("Entregas com situação de prazo correta", int(((entregues["situacao_sla"] == "no_prazo") == prazo_real).sum())),
    ], columns=["verificacao", "remessas"])
    log.info("gabarito: %s", dict(zip(resultado["verificacao"], resultado["remessas"])))
    return resultado
