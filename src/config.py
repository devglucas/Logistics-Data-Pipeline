"""Caminhos, calendário e parâmetros do pipeline."""

from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT_DIR / "data" / "raw"
REFERENCIA_DIR = RAW_DIR / "referencia"
EXTERNAL_DIR = ROOT_DIR / "data" / "external"
BANCO = ROOT_DIR / "data" / "warehouse" / "logistica.db"
SQL_DIR = ROOT_DIR / "sql"
OUTPUT_DIR = ROOT_DIR / "output"
REPORTS_DIR = OUTPUT_DIR / "reports"
CHARTS_DIR = OUTPUT_DIR / "charts"

FERIADOS = pd.to_datetime(["2024-12-25", "2025-01-01", "2025-03-03", "2025-03-04", "2025-04-18", "2025-04-21",
                           "2025-05-01", "2025-06-19"])
CALENDARIO_INICIO, CALENDARIO_FIM = "2024-12-01", "2025-06-30"

# Evento com data fora desta janela em relação ao lote é relógio errado
DIAS_MAXIMOS_ATRASO_EVENTO = 30

PESO_MAXIMO_KG = 500
