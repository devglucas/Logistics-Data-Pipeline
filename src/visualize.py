"""Gráficos de prazo, gargalos, backlog e saúde da carga."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from src.config import CHARTS_DIR  # noqa: E402
from src.utils import configurar_logger, formatar_br  # noqa: E402

log = configurar_logger("visualize")

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
CINZA, TINTA_2, TINTA_3 = "#b5b3ab", "#52514e", "#898781"
GRADE, EIXO, SUPERFICIE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
RAMPA_AZUL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
    "axes.edgecolor": EIXO, "axes.labelcolor": TINTA_2, "axes.titlecolor": "#0b0b0b",
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 24,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRADE, "grid.linewidth": 0.6,
    "xtick.color": TINTA_3, "ytick.color": TINTA_3, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "legend.frameon": False, "legend.fontsize": 9, "font.family": "sans-serif",
})
pct = FuncFormatter(lambda v, _: f"{v:.0f}%")


def _subtitulo(ax, texto: str) -> None:
    ax.text(0, 1.02, texto, transform=ax.transAxes, fontsize=9, color=TINTA_2, va="bottom")


def _salvar(fig, nome: str) -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / nome, dpi=150)
    plt.close(fig)


def _semana(data: str) -> str:
    return f"{data[8:10]}/{MESES[int(data[5:7]) - 1]}"


def grafico_otd_semanal(semanal: pd.DataFrame) -> None:
    dados = semanal[semanal["entregues"] >= 100]  # semanas parciais nas pontas distorcem a taxa
    x = np.arange(len(dados))
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.plot(x, dados["otd_pct"], color=CINZA, linewidth=1.5, marker="o", markersize=4, label="Semana")
    ax.plot(x, dados["otd_media_4_semanas"], color=SERIES[0], linewidth=2.5, label="Média móvel de 4 semanas")
    ax.set_xticks(x, [_semana(s) for s in dados["ano_semana"]], rotation=45, ha="right")
    ax.yaxis.set_major_formatter(pct)
    ax.set_ylim(80, 100)
    ax.set_yticks(range(80, 101, 5))
    ax.set_title("Entregas no prazo por semana (OTD)")
    _subtitulo(ax, "Semana da entrega · eixo de 80% a 100%")
    ax.legend(loc="lower left", ncol=2)
    _salvar(fig, "01_otd_semanal.png")


def grafico_otd_servico_regiao(tabela: pd.DataFrame) -> None:
    matriz = tabela.pivot(index="servico", columns="regiao_destino", values="otd_pct").reindex(["expresso", "padrao", "economico"])
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    ax.imshow(matriz.to_numpy(dtype=float), aspect="auto", vmin=60, vmax=100,
              cmap=LinearSegmentedColormap.from_list("azul", RAMPA_AZUL))
    for (i, j), valor in np.ndenumerate(matriz.to_numpy(dtype=float)):
        ax.text(j, i, f"{valor:.0f}%", ha="center", va="center", fontsize=10, color="white" if valor >= 85 else TINTA_2)
    ax.set_xticks(range(matriz.shape[1]), matriz.columns)
    ax.set_yticks(range(3), ["Expresso", "Padrão", "Econômico"])
    ax.tick_params(length=0)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("OTD por serviço e região de destino")
    _subtitulo(ax, "Cores de 60% a 100%")
    _salvar(fig, "02_otd_servico_regiao.png")


def grafico_otd_hub(hubs: pd.DataFrame) -> None:
    dados = hubs.sort_values("otd_pct", ascending=False).iloc[::-1]
    cores = dados["operador"].map({"propria": SERIES[0], "parceira": SERIES[1]})
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    barras = ax.barh(dados["cidade"], dados["otd_pct"], color=cores, height=0.65, zorder=2)
    for barra, valor in zip(barras, dados["otd_pct"]):
        ax.text(barra.get_width(), barra.get_y() + barra.get_height() / 2, f"  {formatar_br(float(valor), 1)}%", va="center",
                fontsize=8.5, color=TINTA_2)
    ax.set_xlim(70, 102)
    ax.xaxis.set_major_formatter(pct)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_title("OTD por hub de destino")
    _subtitulo(ax, "Eixo começa em 70% · azul: operação própria · laranja: parceira")
    _salvar(fig, "03_otd_hub.png")


def grafico_permanencia(semanal: pd.DataFrame) -> None:
    pivot = semanal[semanal["passagens"] >= 5].pivot(index="ano_semana", columns="hub_id", values="horas_medias")
    x = np.arange(len(pivot))
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for hub in pivot.columns:
        if hub != "REC":
            ax.plot(x, pivot[hub], color=CINZA, linewidth=1, alpha=0.7)
    ax.plot([], [], color=CINZA, linewidth=1, label="Demais hubs")
    ax.plot(x, pivot["REC"], color=SERIES[1], linewidth=2.5, marker="o", markersize=4, label="Recife")
    ax.set_xticks(x, [_semana(s) for s in pivot.index], rotation=45, ha="right")
    ax.set_ylabel("Horas")
    ax.set_ylim(0)
    ax.set_title("Tempo médio parado no hub por semana")
    _subtitulo(ax, "Do recebimento até o evento seguinte no mesmo hub")
    ax.legend(loc="upper right")
    _salvar(fig, "04_permanencia_hubs.png")


def grafico_backlog(backlog: pd.DataFrame) -> None:
    datas = pd.to_datetime(backlog["data"])
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(datas, backlog["em_aberto"], color=SERIES[0], alpha=0.15)
    ax.plot(datas, backlog["em_aberto"], color=SERIES[0], linewidth=2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: (lambda d: f"{d.day:02d}/{MESES[d.month - 1]}")(matplotlib.dates.num2date(v))))
    ax.set_ylim(0)
    ax.set_title("Remessas em aberto no fim de cada dia")
    _subtitulo(ax, "Postadas e ainda não encerradas")
    _salvar(fig, "05_backlog_diario.png")


def grafico_latencia(latencia: pd.DataFrame) -> None:
    pivot = latencia.assign(faixa=latencia["dias_de_atraso"].clip(upper=3)).pivot_table(
        index="fonte", columns="faixa", values="pct_da_fonte", aggfunc="sum", fill_value=0).reindex(columns=[0, 1, 2, 3], fill_value=0)
    rotulos = {0: "No mesmo dia", 1: "D+1", 2: "D+2", 3: "D+3 ou mais"}
    fig, ax = plt.subplots(figsize=(9, 3))
    base = np.zeros(len(pivot))
    for coluna, cor in zip(pivot.columns, SERIES):
        ax.barh(pivot.index.map({"proprio": "Hubs próprios", "parceiro": "Parceira"}), pivot[coluna], left=base, color=cor,
                label=rotulos[coluna], height=0.55, edgecolor=SUPERFICIE, linewidth=1, zorder=2)
        base += pivot[coluna].to_numpy()
    ax.xaxis.set_major_formatter(pct)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_title("Em quantos dias o evento chega ao warehouse")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=4)
    _salvar(fig, "06_latencia_dos_dados.png")


def gerar_graficos(t: dict) -> None:
    grafico_otd_semanal(t["evolucao_semanal"])
    grafico_otd_servico_regiao(t["sla_servico_regiao"])
    grafico_otd_hub(t["sla_hub_destino"])
    grafico_permanencia(t["permanencia_semanal"])
    grafico_backlog(t["backlog_diario"])
    grafico_latencia(t["latencia_dos_dados"])
    log.info("6 gráficos salvos em output/charts")
