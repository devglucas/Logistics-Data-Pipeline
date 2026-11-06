"""
Gerador de dados sintéticos da transportadora "Rota Sul Encomendas".

Simula a rede de 12 hubs, a viagem de cada remessa e a chegada dos dados em lotes
diários, particionados por data de chegada (estilo Hive):

    data/raw/dt=2025-01-02/remessas.csv              remessas informadas pelo sistema comercial
    data/raw/dt=2025-01-02/eventos_proprios.jsonl.gz leitores dos hubs próprios (timestamp com fuso)
    data/raw/dt=2025-01-02/eventos_parceiro.csv.gz   parceira do Norte/Nordeste (hora local, sem fuso)
    data/raw/referencia/                             hubs, clientes e matriz de prazos
    data/external/gabarito_entregas.csv              resultado verdadeiro de cada remessa

Como em um sistema real, o dado não chega arrumado:
- eventos ATRASADOS: o evento aparece em um lote dias depois de acontecer
- eventos DUPLICADOS entre lotes (reenvio) e FORA DE ORDEM
- eventos ÓRFÃOS: chegam antes da remessa que os explica
- remessas REENVIADAS com peso corrigido
- relógios errados (ano de 2035, 1970), hubs desconhecidos, pesos inválidos
- códigos, separadores, fusos e formatos de data diferentes entre os sistemas

O gabarito serve apenas para medir o resultado do pipeline. Dados fictícios.

Uso:
    python scripts/generate_data.py
"""

from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 505
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
EXTERNAL_DIR = ROOT / "data" / "external"

PRIMEIRO_LOTE, ULTIMO_LOTE = pd.Timestamp("2025-01-02"), pd.Timestamp("2025-03-31")
ULTIMA_POSTAGEM = pd.Timestamp("2025-03-28")
FERIADOS = pd.to_datetime(["2025-01-01", "2025-03-03", "2025-03-04", "2025-04-18", "2025-04-21", "2025-05-01"])
DU = pd.offsets.CustomBusinessDay(holidays=FERIADOS)

# código, cidade, UF, região, fuso, operador, peso como origem, peso como destino
HUBS = [
    ("SAO", "Guarulhos", "SP", "Sudeste", "America/Sao_Paulo", "propria", 45, 22),
    ("RIO", "Rio de Janeiro", "RJ", "Sudeste", "America/Sao_Paulo", "propria", 12, 13),
    ("BHZ", "Belo Horizonte", "MG", "Sudeste", "America/Sao_Paulo", "propria", 10, 10),
    ("CWB", "Curitiba", "PR", "Sul", "America/Sao_Paulo", "propria", 12, 9),
    ("POA", "Porto Alegre", "RS", "Sul", "America/Sao_Paulo", "propria", 8, 8),
    ("BSB", "Brasília", "DF", "Centro-Oeste", "America/Sao_Paulo", "propria", 5, 7),
    ("CGB", "Cuiabá", "MT", "Centro-Oeste", "America/Cuiaba", "propria", 2, 4),
    ("SSA", "Salvador", "BA", "Nordeste", "America/Bahia", "parceira", 2, 8),
    ("REC", "Recife", "PE", "Nordeste", "America/Recife", "parceira", 2, 7),
    ("FOR", "Fortaleza", "CE", "Nordeste", "America/Fortaleza", "parceira", 1, 6),
    ("MAO", "Manaus", "AM", "Norte", "America/Manaus", "parceira", 1, 4),
    ("RBR", "Rio Branco", "AC", "Norte", "America/Rio_Branco", "parceira", 0, 2),
]
HUB = {h[0]: dict(zip(["codigo", "cidade", "uf", "regiao", "fuso", "operador", "p_origem", "p_destino"], h)) for h in HUBS}

SERVICOS = {"expresso": 1, "padrao": 3, "economico": 4}  # prazo base em dias úteis
EXTRA_REGIAO = {("Sul", "Sudeste"): 1, ("Sudeste", "Centro-Oeste"): 1, ("Sul", "Centro-Oeste"): 2,
                ("Sudeste", "Nordeste"): 2, ("Centro-Oeste", "Nordeste"): 2, ("Sul", "Nordeste"): 3,
                ("Sudeste", "Norte"): 3, ("Centro-Oeste", "Norte"): 3, ("Nordeste", "Norte"): 3, ("Sul", "Norte"): 4}
HORAS_TRANSITO = {("Sudeste", "Sudeste"): 10, ("Sul", "Sudeste"): 16, ("Sudeste", "Centro-Oeste"): 22,
                  ("Sul", "Sul"): 10, ("Centro-Oeste", "Centro-Oeste"): 18, ("Sul", "Centro-Oeste"): 30,
                  ("Sudeste", "Nordeste"): 40, ("Centro-Oeste", "Nordeste"): 34, ("Nordeste", "Nordeste"): 14,
                  ("Sul", "Nordeste"): 52, ("Sudeste", "Norte"): 62, ("Centro-Oeste", "Norte"): 48,
                  ("Nordeste", "Norte"): 56, ("Sul", "Norte"): 72, ("Norte", "Norte"): 30}

CODIGOS_PARCEIRO = {"RECEBIDO_HUB": "REC", "SAIU_HUB": "EXP", "SAIU_ENTREGA": "OUT", "TENTATIVA_FALHA": "NOK",
                    "ENTREGUE": "DLV", "EXTRAVIADO": "LOST", "DEVOLVIDO": "RTN", "POSTADO": "POS", "COLETADO": "COL"}
VARIANTES_SERVICO = {"expresso": ["expresso", "EXPRESSO", "Expresso", "EXP"], "padrao": ["padrao", "Padrão", "PADRAO", "STD"],
                     "economico": ["economico", "Econômico", "ECONOMICO", "ECO"]}


def par(a: str, b: str, tabela: dict, padrao=0):
    return tabela.get((a, b), tabela.get((b, a), padrao))


def prazo_dias_uteis(servico: str, regiao_o: str, regiao_d: str) -> int:
    return SERVICOS[servico] + par(regiao_o, regiao_d, EXTRA_REGIAO)


def rota(origem: str, destino: str) -> list[str]:
    if origem == destino:
        return [origem]
    if "SAO" in (origem, destino):
        return [origem, destino]
    central = "BSB" if destino in ("CGB", "MAO", "RBR") and origem != "BSB" else "SAO"
    return [origem, destino] if central in (origem, destino) else [origem, central, destino]


def congestionamento(hub: str, quando: pd.Timestamp) -> float:
    """Multiplicador do tempo parado no hub: chuvas em Recife, Carnaval e operação parceira."""
    fator = 1.4 if HUB[hub]["operador"] == "parceira" else 1.0
    if hub == "REC" and pd.Timestamp("2025-02-10", tz="UTC") <= quando <= pd.Timestamp("2025-02-24", tz="UTC"):
        fator *= 7
    if pd.Timestamp("2025-02-28", tz="UTC") <= quando <= pd.Timestamp("2025-03-06", tz="UTC"):
        fator *= 2.5
    return fator


def horario_local(data_local: pd.Timestamp, hora: float, fuso: str) -> pd.Timestamp:
    return (data_local.normalize() + pd.Timedelta(hours=hora)).tz_localize(fuso).tz_convert("UTC")


def proxima_manha(ts: pd.Timestamp, fuso: str, rng) -> pd.Timestamp:
    """Saída para entrega: manhã seguinte à chegada, de segunda a sábado."""
    dia = ts.tz_convert(fuso).tz_localize(None).normalize() + pd.Timedelta(days=1)
    if dia.dayofweek == 6 or dia in FERIADOS:
        dia += pd.Timedelta(days=1)
    return horario_local(dia, rng.uniform(7.5, 10.5), fuso)


def simular_remessa(rng, remessa: dict) -> tuple[list[dict], dict]:
    """Devolve os eventos verdadeiros da remessa e o seu desfecho."""
    origem, destino, servico = remessa["hub_origem"], remessa["hub_destino"], remessa["servico"]
    t = remessa["postado_utc"]
    eventos = [("POSTADO", origem, t)]
    t += pd.Timedelta(hours=rng.uniform(1, 6))
    eventos.append(("COLETADO", origem, t))
    caminho = rota(origem, destino)
    velocidade = {"expresso": 0.35, "padrao": 1.35, "economico": 2.1}[servico]
    desfecho = {"status": "em_transito", "entregue_utc": None}

    for i, hub in enumerate(caminho):
        if i > 0:
            horas = par(HUB[caminho[i - 1]]["regiao"], HUB[hub]["regiao"], HORAS_TRANSITO, 24) * velocidade
            t += pd.Timedelta(hours=horas * rng.uniform(0.85, 1.35))
        eventos.append(("RECEBIDO_HUB", hub, t))
        if rng.random() < 0.004:  # extravio dentro do hub
            eventos.append(("EXTRAVIADO", hub, t + pd.Timedelta(hours=rng.uniform(24, 72))))
            desfecho["status"] = "extraviado"
            return eventos, desfecho
        t += pd.Timedelta(hours=rng.uniform(2, 12) * congestionamento(hub, t) * (0.6 if servico == "expresso" else 1))
        if i < len(caminho) - 1:
            eventos.append(("SAIU_HUB", hub, t))

    fuso = HUB[destino]["fuso"]
    for tentativa in range(3):
        t = proxima_manha(t, fuso, rng)
        eventos.append(("SAIU_ENTREGA", destino, t))
        t += pd.Timedelta(hours=rng.uniform(1, 8))
        if rng.random() < (0.20 if HUB[destino]["operador"] == "parceira" else 0.10):
            eventos.append(("TENTATIVA_FALHA", destino, t))
            continue
        eventos.append(("ENTREGUE", destino, t))
        desfecho.update(status="entregue", entregue_utc=t)
        return eventos, desfecho
    eventos.append(("DEVOLVIDO", destino, t + pd.Timedelta(hours=rng.uniform(24, 48))))
    desfecho["status"] = "devolvido"
    return eventos, desfecho


def gerar_remessas(rng, clientes: pd.DataFrame) -> list[dict]:
    origens = [h for h in HUB if HUB[h]["p_origem"] > 0]
    p_origem = np.array([HUB[h]["p_origem"] for h in origens], dtype=float)
    destinos = list(HUB)
    p_destino = np.array([HUB[h]["p_destino"] for h in destinos], dtype=float)
    peso_cliente = rng.lognormal(0, 1, len(clientes))
    remessas, seq = [], 100_000
    for dia in pd.date_range(PRIMEIRO_LOTE, ULTIMA_POSTAGEM, freq="D"):
        if dia.dayofweek == 6 or dia in FERIADOS:
            continue
        n = rng.poisson(120 if dia.dayofweek < 5 else 45)
        for _ in range(n):
            seq += int(rng.integers(1, 4))
            origem = str(rng.choice(origens, p=p_origem / p_origem.sum()))
            destino = str(rng.choice(destinos, p=p_destino / p_destino.sum()))
            servico = str(rng.choice(list(SERVICOS), p=[0.2, 0.55, 0.25]))
            remessas.append({
                "remessa_id": f"BR{seq:07d}",
                "cliente_id": str(clientes["cliente_id"].iat[rng.choice(len(clientes), p=peso_cliente / peso_cliente.sum())]),
                "servico": servico, "hub_origem": origem, "hub_destino": destino,
                "cep_destino": f"{rng.integers(1000000, 99999999):08d}",
                "peso_kg": round(float(rng.lognormal(0.6, 0.9)), 2),
                "valor_frete": 0.0, "postado_utc": horario_local(dia, rng.uniform(8, 18), HUB[origem]["fuso"]),
            })
            r = remessas[-1]
            r["valor_frete"] = round(12 + r["peso_kg"] * 2.1 + prazo_dias_uteis(servico, HUB[origem]["regiao"], HUB[destino]["regiao"]) * 3.5
                                     + {"expresso": 25, "padrao": 8, "economico": 0}[servico], 2)
    return remessas


# --------------------------------------------------------------------------- #
# Entrega dos dados em lotes
# --------------------------------------------------------------------------- #
def formatar_proprio(rng, remessa_id: str, codigo: str, hub: str, ts: pd.Timestamp, n: int) -> dict:
    if rng.random() < 0.5:
        carimbo = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        local = ts.tz_convert(HUB[hub]["fuso"])
        carimbo = local.strftime("%Y-%m-%dT%H:%M:%S%z")
        carimbo = carimbo[:-2] + ":" + carimbo[-2:]
    return {"id_evento": f"EV{n:08d}", "remessa": remessa_id, "codigo": codigo, "hub": hub, "ts": carimbo,
            "dispositivo": f"{hub}-{rng.integers(1, 9):02d}"}


def formatar_parceiro(rng, remessa_id: str, codigo: str, hub: str, ts: pd.Timestamp) -> dict:
    local = ts.tz_convert(HUB[hub]["fuso"])  # a parceira grava a hora local da base, sem fuso
    awb = remessa_id if rng.random() > 0.05 else f" {remessa_id.lower()}"
    status = CODIGOS_PARCEIRO[codigo]
    return {"awb": awb, "status": status if rng.random() > 0.1 else status.lower(),
            "base": hub if rng.random() > 0.1 else hub.lower(), "data_hora": local.strftime("%d/%m/%Y %H:%M")}


def distribuir_em_lotes(rng, remessas: list[dict], eventos: list[tuple]) -> dict:
    lotes: dict[pd.Timestamp, dict] = {d: {"remessas": [], "proprios": [], "parceiro": []}
                                       for d in pd.date_range(PRIMEIRO_LOTE, ULTIMO_LOTE, freq="D")}

    def lote_de(dia: pd.Timestamp):
        return lotes.get(dia)

    for r in remessas:
        dia = r["postado_utc"].tz_convert(HUB[r["hub_origem"]]["fuso"]).tz_localize(None).normalize()
        atraso = 1 if rng.random() < 0.015 else 0  # remessa chega depois dos primeiros eventos (órfãos)
        destino = lote_de(dia + pd.Timedelta(days=atraso))
        local = r["postado_utc"].tz_convert(HUB[r["hub_origem"]]["fuso"]).tz_localize(None)
        registro = {
            "remessa_id": r["remessa_id"], "cliente_id": r["cliente_id"] if rng.random() > 0.03 else f" {r['cliente_id']} ",
            "servico": str(rng.choice(VARIANTES_SERVICO[r["servico"]])), "hub_origem": r["hub_origem"],
            "hub_destino": r["hub_destino"],
            "cep_destino": r["cep_destino"] if rng.random() < 0.6 else f"{r['cep_destino'][:5]}-{r['cep_destino'][5:]}",
            "peso_kg": f"{r['peso_kg']}".replace(".", ",") if rng.random() < 0.3 else str(r["peso_kg"]),
            "valor_frete": f"{r['valor_frete']:.2f}", "postado_em": local.strftime("%Y-%m-%d %H:%M:%S"),
            "atualizado_em": local.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if rng.random() < 0.003:
            registro["peso_kg"] = str(rng.choice(["0", "9999", "-1"]))
        if destino is not None:
            destino["remessas"].append(registro)
        if rng.random() < 0.02:  # peso revisado na balança do hub: remessa reenviada dias depois
            novo = dict(registro, peso_kg=str(round(r["peso_kg"] * rng.uniform(1.05, 1.4), 2)))
            reenvio = dia + pd.Timedelta(days=int(rng.integers(1, 4)))
            novo["atualizado_em"] = (reenvio + pd.Timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")
            if lote_de(reenvio) is not None:
                lote_de(reenvio)["remessas"].append(novo)

    corte = pd.Timestamp(ULTIMO_LOTE, tz="America/Sao_Paulo") + pd.Timedelta(days=1)
    for n, (remessa_id, codigo, hub, ts) in enumerate(eventos, start=1):
        if ts >= corte:
            continue
        parceiro = HUB[hub]["operador"] == "parceira"
        dia = ts.tz_convert("America/Sao_Paulo").tz_localize(None).normalize()
        atraso = 1 if parceiro else 0                       # parceira envia em lote no dia seguinte
        if rng.random() < (0.08 if parceiro else 0.03):
            atraso += int(rng.integers(1, 5))               # evento atrasado
        chave = "parceiro" if parceiro else "proprios"
        registro = (formatar_parceiro(rng, remessa_id, codigo, hub, ts) if parceiro
                    else formatar_proprio(rng, remessa_id, codigo, hub, ts, n))
        r = rng.random()
        if not parceiro and r < 0.002:                      # relógio do leitor errado
            registro["ts"] = str(rng.choice(["2035-01-01T00:00:00Z", "1970-01-01T00:00:00Z"]))
        elif r < 0.004:                                     # hub digitado errado
            registro["hub" if not parceiro else "base"] = str(rng.choice(["XXX", "SA0", "RC"]))
        alvo = lote_de(dia + pd.Timedelta(days=atraso))
        if alvo is not None:
            alvo[chave].append(registro)
        if rng.random() < 0.015:                            # reenvio: o mesmo evento em outro lote
            duplicado = lote_de(dia + pd.Timedelta(days=atraso + int(rng.integers(0, 3))))
            if duplicado is not None:
                duplicado[chave].append(registro)
    return lotes


def gravar_gzip(caminho: Path, conteudo: str) -> None:
    # mtime=0: o mesmo conteúdo gera sempre os mesmos bytes (hash do lote estável)
    with open(caminho, "wb") as bruto, gzip.GzipFile(filename="", mode="wb", fileobj=bruto, mtime=0) as arquivo:
        arquivo.write(conteudo.encode("utf-8"))


def gravar_lotes(lotes: dict) -> None:
    for dia, lote in lotes.items():
        pasta = RAW_DIR / f"dt={dia:%Y-%m-%d}"
        pasta.mkdir(parents=True)
        colunas = ["remessa_id", "cliente_id", "servico", "hub_origem", "hub_destino", "cep_destino", "peso_kg",
                   "valor_frete", "postado_em", "atualizado_em"]
        pd.DataFrame(lote["remessas"], columns=colunas).to_csv(pasta / "remessas.csv", index=False)
        gravar_gzip(pasta / "eventos_proprios.jsonl.gz",
                    "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in lote["proprios"]))
        linhas = ["awb;status;base;data_hora"] + [f"{e['awb']};{e['status']};{e['base']};{e['data_hora']}" for e in lote["parceiro"]]
        gravar_gzip(pasta / "eventos_parceiro.csv.gz", "\n".join(linhas) + "\n")


def data_limite(postado_utc: pd.Timestamp, hub_origem: str, prazo: int) -> pd.Timestamp:
    dia = postado_utc.tz_convert(HUB[hub_origem]["fuso"]).tz_localize(None).normalize()
    return DU.rollforward(dia) + DU * prazo


def main() -> None:
    rng = np.random.default_rng(SEED)
    shutil.rmtree(RAW_DIR, ignore_errors=True)
    (RAW_DIR / "referencia").mkdir(parents=True)
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)

    clientes = pd.DataFrame({
        "cliente_id": [f"C{i:04d}" for i in range(1, 201)],
        "nome": [f"Loja Virtual {i:04d}" for i in range(1, 201)],
        "segmento": rng.choice(["Moda", "Eletrônicos", "Casa", "Saúde", "Livros"], 200),
    })
    remessas = gerar_remessas(rng, clientes)

    eventos, gabarito = [], []
    corte = pd.Timestamp(ULTIMO_LOTE, tz="America/Sao_Paulo") + pd.Timedelta(days=1)
    for r in remessas:
        trajetoria, desfecho = simular_remessa(rng, r)
        eventos += [(r["remessa_id"], codigo, hub, ts) for codigo, hub, ts in trajetoria]
        prazo = prazo_dias_uteis(r["servico"], HUB[r["hub_origem"]]["regiao"], HUB[r["hub_destino"]]["regiao"])
        limite = data_limite(r["postado_utc"], r["hub_origem"], prazo)
        entregue = desfecho["entregue_utc"]
        entregue = entregue if entregue is not None and entregue < corte else None
        local = entregue.tz_convert(HUB[r["hub_destino"]]["fuso"]).tz_localize(None).normalize() if entregue is not None else None
        gabarito.append({"remessa_id": r["remessa_id"], "status_final": desfecho["status"] if (entregue is not None or desfecho["status"] != "entregue") else "em_transito",
                         "prazo_dias_uteis": prazo, "data_limite": limite.date(),
                         "entregue_em_utc": entregue.strftime("%Y-%m-%dT%H:%M:%SZ") if entregue is not None else None,
                         "data_entrega_local": local.date() if local is not None else None,
                         "no_prazo": (local <= limite) if local is not None else None})

    gravar_lotes(distribuir_em_lotes(rng, remessas, eventos))

    pd.DataFrame([{k: h[k] for k in ["codigo", "cidade", "uf", "regiao", "fuso", "operador"]} for h in HUB.values()]) \
        .to_csv(RAW_DIR / "referencia" / "hubs.csv", index=False)
    clientes.to_csv(RAW_DIR / "referencia" / "clientes.csv", index=False)
    regioes = sorted({h["regiao"] for h in HUB.values()})
    pd.DataFrame([{"servico": s, "regiao_origem": a, "regiao_destino": b, "prazo_dias_uteis": prazo_dias_uteis(s, a, b)}
                  for s in SERVICOS for a in regioes for b in regioes]).to_csv(RAW_DIR / "referencia" / "sla_servico.csv", index=False)
    gab = pd.DataFrame(gabarito)
    gab.to_csv(EXTERNAL_DIR / "gabarito_entregas.csv", index=False)

    tamanho = sum(f.stat().st_size for f in RAW_DIR.rglob("*") if f.is_file()) / 1024 / 1024
    print(f"Remessas: {len(remessas):,} | eventos: {len(eventos):,} | lotes: {len(list(RAW_DIR.glob('dt=*')))} | {tamanho:.1f} MB")
    print(gab["status_final"].value_counts().to_dict(), "| no prazo:", round(gab["no_prazo"].dropna().astype(bool).mean() * 100, 1), "%")


if __name__ == "__main__":
    main()
