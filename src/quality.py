"""
Testes de qualidade em SQL.

Cada arquivo de sql/tests é uma consulta que deve voltar VAZIA: as linhas devolvidas são
as falhas. O prefixo define a severidade: critica_* interrompe o pipeline e alerta_* é
apenas registrado.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

from src.config import SQL_DIR
from src.db import consultar
from src.utils import configurar_logger

log = configurar_logger("quality")


class ErroDeQualidade(Exception):
    pass


def executar_testes(conexao: sqlite3.Connection) -> pd.DataFrame:
    linhas = []
    for arquivo in sorted((SQL_DIR / "tests").glob("*.sql")):
        severidade, nome = arquivo.stem.split("_", 1)
        falhas = consultar(conexao, arquivo.read_text(encoding="utf-8"))
        linhas.append({"teste": nome, "severidade": severidade, "falhas": len(falhas), "passou": falhas.empty})
    return pd.DataFrame(linhas).sort_values(["severidade", "teste"], ascending=[False, True]).reset_index(drop=True)


def garantir_qualidade(resultado: pd.DataFrame) -> None:
    for teste in resultado.query("not passou").itertuples():
        nivel = log.error if teste.severidade == "critica" else log.warning
        nivel("[%s] %s: %d", teste.severidade, teste.teste, teste.falhas)
    criticas = resultado.query("severidade == 'critica' and not passou")
    if not criticas.empty:
        raise ErroDeQualidade(f"testes críticos falharam: {criticas['teste'].tolist()}")
    log.info("%d testes executados: todos os críticos passaram (%d alertas)", len(resultado), (~resultado["passou"]).sum())
