"""
Extração: descobre quais lotes faltam processar e lê os arquivos de cada um.

Os lotes ficam em partições por data de chegada (dt=AAAA-MM-DD). Um lote é pendente
se nunca foi processado ou se o hash dos arquivos mudou (a fonte reenviou o dia).
"""

from __future__ import annotations

import gzip
import hashlib
import sqlite3
from pathlib import Path

import pandas as pd

from src.config import RAW_DIR, REFERENCIA_DIR

ARQUIVOS_LOTE = ["remessas.csv", "eventos_proprios.jsonl.gz", "eventos_parceiro.csv.gz"]
COLUNAS_PROPRIOS = ["id_evento", "remessa", "codigo", "hub", "ts", "dispositivo"]


def hash_lote(pasta: Path) -> str:
    resumo = hashlib.sha256()
    for nome in ARQUIVOS_LOTE:
        resumo.update((pasta / nome).read_bytes())
    return resumo.hexdigest()


def lotes_pendentes(conexao: sqlite3.Connection, ate: str | None = None, raiz: Path = RAW_DIR) -> list[tuple[str, Path, str]]:
    """Devolve (dt, pasta, hash) dos lotes a processar, em ordem de data."""
    processados = dict(conexao.execute("SELECT dt, hash_arquivos FROM etl_lote").fetchall())
    pendentes = []
    for pasta in sorted(raiz.glob("dt=*")):
        dt = pasta.name.removeprefix("dt=")
        if ate is not None and dt > ate:
            continue
        hash_atual = hash_lote(pasta)
        if processados.get(dt) != hash_atual:
            pendentes.append((dt, pasta, hash_atual))
    return pendentes


def ler_lote(pasta: Path) -> dict[str, pd.DataFrame]:
    proprios = pasta / "eventos_proprios.jsonl.gz"
    with gzip.open(proprios, "rb") as arquivo:
        tem_eventos = bool(arquivo.read(1))  # dia sem leituras gera um arquivo vazio
    eventos = (pd.read_json(proprios, lines=True, compression="gzip", dtype=False, convert_dates=False) if tem_eventos
               else pd.DataFrame(columns=COLUNAS_PROPRIOS))
    return {
        "remessas": pd.read_csv(pasta / "remessas.csv", dtype="string"),
        "proprios": eventos.astype({c: "string" for c in COLUNAS_PROPRIOS}),
        "parceiro": pd.read_csv(pasta / "eventos_parceiro.csv.gz", sep=";", compression="gzip", dtype="string"),
    }


def ler_referencias() -> dict[str, pd.DataFrame]:
    return {nome: pd.read_csv(REFERENCIA_DIR / f"{nome}.csv", dtype={"cliente_id": "string"})
            for nome in ["hubs", "clientes", "sla_servico"]}
