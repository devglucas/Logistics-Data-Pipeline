"""
Orquestrador do warehouse de logística.

    lotes pendentes -> limpeza -> carga incremental -> testes de qualidade em SQL
                    -> análises em SQL -> relatório e gráficos

Uso:
    python main.py                     processa tudo o que estiver pendente
    python main.py --ate 2025-02-15    processa só até esta data (simula a operação diária)
    python main.py --reset             apaga o banco e recarrega do zero
"""

from __future__ import annotations

import argparse
import time

from src.analyze import executar_analises
from src.config import BANCO
from src.db import conectar, criar_esquema
from src.evaluate import avaliar
from src.extract import lotes_pendentes
from src.load import carregar_dimensoes, processar_lote
from src.quality import executar_testes, garantir_qualidade
from src.report import exportar_tabelas, gerar_relatorio
from src.utils import configurar_logger
from src.visualize import gerar_graficos

log = configurar_logger("pipeline")


def executar_pipeline(ate: str | None = None, reset: bool = False) -> None:
    inicio = time.perf_counter()
    if reset:
        BANCO.unlink(missing_ok=True)
    conexao = conectar()
    criar_esquema(conexao)
    hubs = carregar_dimensoes(conexao)

    pendentes = lotes_pendentes(conexao, ate)
    log.info("%d lotes pendentes", len(pendentes))
    for lote in pendentes:
        resumo = processar_lote(conexao, *lote, hubs)
        log.debug("lote %s: %d eventos novos", resumo["dt"], resumo["eventos_novos"])

    testes = executar_testes(conexao)
    garantir_qualidade(testes)  # interrompe aqui se algum teste crítico falhar

    analises = executar_analises(conexao)
    tabelas = exportar_tabelas(conexao, analises, testes, avaliar(conexao))
    gerar_relatorio(tabelas)
    gerar_graficos(tabelas)
    conexao.close()
    log.info("Pipeline concluído em %.1fs", time.perf_counter() - inicio)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ate", help="processa lotes só até esta data (AAAA-MM-DD)")
    parser.add_argument("--reset", action="store_true", help="apaga o banco antes de carregar")
    argumentos = parser.parse_args()
    executar_pipeline(argumentos.ate, argumentos.reset)
