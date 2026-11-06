"""
Acesso ao banco.

Cada lote precisa ser atômico: ou entra inteiro, ou não entra. Dois atalhos comuns
quebrariam isso, porque fazem commit por conta própria no meio da transação:
`sqlite3.executescript` e `DataFrame.to_sql`. Por isso os arquivos .sql são
executados comando a comando e os DataFrames são inseridos com `executemany`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.config import BANCO, SQL_DIR


def conectar(caminho: Path | str = BANCO) -> sqlite3.Connection:
    if caminho != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def comandos_sql(texto: str) -> list[str]:
    """Separa um script em comandos completos (respeita ';' dentro de textos e comentários)."""
    comandos, atual = [], ""
    for linha in texto.splitlines(keepends=True):
        atual += linha
        if sqlite3.complete_statement(atual):
            if atual.strip():
                comandos.append(atual)
            atual = ""
    return comandos


def executar_arquivo(conexao: sqlite3.Connection, caminho: Path, parametros: dict | None = None) -> None:
    for comando in comandos_sql(caminho.read_text(encoding="utf-8")):
        conexao.execute(comando, parametros or {})


def criar_esquema(conexao: sqlite3.Connection) -> None:
    with conexao:
        for arquivo in sorted((SQL_DIR / "schema").glob("*.sql")):
            executar_arquivo(conexao, arquivo)


def inserir(conexao: sqlite3.Connection, tabela: str, df: pd.DataFrame, modo: str = "INSERT") -> int:
    """Insere um DataFrame sem commit. NaN/NaT viram NULL."""
    if df.empty:
        return 0
    colunas = ", ".join(df.columns)
    marcadores = ", ".join("?" for _ in df.columns)
    linhas = df.astype(object).where(df.notna(), None).itertuples(index=False, name=None)
    cursor = conexao.executemany(f"{modo} INTO {tabela} ({colunas}) VALUES ({marcadores})", linhas)
    return cursor.rowcount


def consultar(conexao: sqlite3.Connection, sql: str, parametros: dict | None = None) -> pd.DataFrame:
    return pd.read_sql_query(sql, conexao, params=parametros)
