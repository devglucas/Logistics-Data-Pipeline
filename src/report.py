"""Relatório em Markdown e exportação das tabelas."""

from __future__ import annotations

import sqlite3

import pandas as pd

from src.config import OUTPUT_DIR, REPORTS_DIR
from src.db import consultar
from src.utils import configurar_logger, df_para_markdown

log = configurar_logger("report")

SQL_LOTES = """
SELECT COUNT(*) AS lotes, MIN(dt) AS primeiro, MAX(dt) AS ultimo, SUM(remessas_lidas) AS remessas_lidas,
       SUM(eventos_lidos) AS eventos_lidos, SUM(eventos_novos) AS eventos_novos,
       SUM(eventos_lidos) - SUM(eventos_novos) AS duplicados_ignorados, SUM(rejeitados) AS rejeitados
FROM etl_lote
"""
SQL_QUARENTENA = "SELECT fonte, motivo, COUNT(*) AS registros FROM quarentena GROUP BY fonte, motivo ORDER BY registros DESC"


def exportar_tabelas(conexao: sqlite3.Connection, analises: dict, testes: pd.DataFrame, avaliacao) -> dict:
    tabelas = {**analises, "testes_qualidade": testes, "resumo_lotes": consultar(conexao, SQL_LOTES),
               "quarentena": consultar(conexao, SQL_QUARENTENA)}
    if avaliacao is not None:
        tabelas["avaliacao_gabarito"] = avaliacao
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for nome, df in tabelas.items():
        df.to_csv(REPORTS_DIR / f"{nome}.csv", index=False)
    log.info("%d tabelas salvas em output/reports", len(tabelas))
    return tabelas


def gerar_relatorio(tabelas: dict) -> None:
    kpis = tabelas["kpis"].T.reset_index()
    kpis.columns = ["indicador", "valor"]
    partes = [
        "# Relatório de logística\n", "_Gerado automaticamente por `python main.py`._\n",
        "## 1. Indicadores\n", df_para_markdown(kpis) + "\n",
        "## 2. Prazo (OTD)\n", "![OTD semanal](charts/01_otd_semanal.png)\n", df_para_markdown(tabelas["sla_mensal"]) + "\n",
        "![OTD serviço x região](charts/02_otd_servico_regiao.png)\n", df_para_markdown(tabelas["sla_servico_regiao"]) + "\n",
        "![OTD por hub](charts/03_otd_hub.png)\n", df_para_markdown(tabelas["sla_hub_destino"]) + "\n",
        "## 3. Gargalos\n", "![Permanência](charts/04_permanencia_hubs.png)\n", df_para_markdown(tabelas["permanencia_hub"]) + "\n",
        "## 4. Lead time\n", df_para_markdown(tabelas["lead_time_percentis"].head(15)) + "\n",
        "## 5. Backlog\n", "![Backlog](charts/05_backlog_diario.png)\n",
        "### Remessas paradas\n", df_para_markdown(tabelas["remessas_paradas"].head(20)) + "\n",
        "## 6. Clientes com pior OTD\n", df_para_markdown(tabelas["clientes_pior_otd"]) + "\n",
        "## 7. Saúde da carga\n", df_para_markdown(tabelas["resumo_lotes"]) + "\n",
        "### Latência dos dados\n", "![Latência](charts/06_latencia_dos_dados.png)\n", df_para_markdown(tabelas["latencia_dos_dados"]) + "\n",
        "### Quarentena\n", df_para_markdown(tabelas["quarentena"]) + "\n",
        "### Testes de qualidade\n", df_para_markdown(tabelas["testes_qualidade"]) + "\n",
    ]
    if "avaliacao_gabarito" in tabelas:
        partes += ["### Comparação com o gabarito\n", df_para_markdown(tabelas["avaliacao_gabarito"]) + "\n"]
    caminho = OUTPUT_DIR / "relatorio.md"
    caminho.write_text("\n".join(partes), encoding="utf-8")
    log.info("relatório salvo em output/%s", caminho.name)
