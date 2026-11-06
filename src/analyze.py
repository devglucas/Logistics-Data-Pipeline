"""Executa as consultas analíticas de sql/analytics: cada arquivo vira uma tabela."""

from __future__ import annotations

import sqlite3

import pandas as pd

from src.config import SQL_DIR
from src.db import consultar
from src.utils import configurar_logger

log = configurar_logger("analyze")


def executar_analises(conexao: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    resultado = {}
    for arquivo in sorted((SQL_DIR / "analytics").glob("*.sql")):
        nome = arquivo.stem.split("_", 1)[1]
        resultado[nome] = consultar(conexao, arquivo.read_text(encoding="utf-8"))
    log.info("%d consultas analíticas executadas", len(resultado))
    return resultado
