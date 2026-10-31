import json
import os
import time
from datetime import datetime, timezone

import requests

PASTA_BRONZE_CNES = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "bronze", "cnes"
)

URL_DETALHE = "https://cnes.datasus.gov.br/services/estabelecimentos/{id}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://cnes.datasus.gov.br/pages/estabelecimentos/consulta.jsp",
}


def arquivo_resumo_mais_recente():
    arquivos = [
        f for f in os.listdir(PASTA_BRONZE_CNES)
        if f.startswith("estabelecimentos_recife_") and f.endswith(".json")
    ]
    arquivos.sort()
    return os.path.join(PASTA_BRONZE_CNES, arquivos[-1])


def carregar_ids_que_atendem_sus():
    caminho = arquivo_resumo_mais_recente()
    with open(caminho, encoding="utf-8") as arquivo:
        estabelecimentos = json.load(arquivo)
    return [e["id"] for e in estabelecimentos if e.get("atendeSus") == "S"]


def buscar_detalhe(id_estabelecimento):
    url = URL_DETALHE.format(id=id_estabelecimento)
    for tentativa in range(3):
        try:
            resposta = requests.get(url, headers=HEADERS, timeout=30)
            resposta.raise_for_status()
            dados = resposta.json()
            # a API pode devolver uma lista com 1 item ou o objeto direto
            return dados[0] if isinstance(dados, list) else dados
        except requests.RequestException:
            if tentativa == 2:
                raise
            time.sleep(tentativa + 1)


def salvar_json(dados, nome_arquivo):
    os.makedirs(PASTA_BRONZE_CNES, exist_ok=True)
    caminho = os.path.join(PASTA_BRONZE_CNES, nome_arquivo)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
    print(f"Arquivo salvo em: {caminho}")


if __name__ == "__main__":
    ids = carregar_ids_que_atendem_sus()
    print(f"{len(ids)} estabelecimentos que atendem SUS. Buscando detalhes...")

    detalhes = []
    falhas = []
    for indice, id_estabelecimento in enumerate(ids, start=1):
        print(f"[{indice}/{len(ids)}] {id_estabelecimento}")
        try:
            detalhes.append(buscar_detalhe(id_estabelecimento))
        except requests.RequestException as erro:
            print(f"  Falhou: {erro}")
            falhas.append(id_estabelecimento)
        time.sleep(0.3)  # não bombardear a API do CNES

    if falhas:
        raise RuntimeError(
            f"Coleta incompleta: {len(falhas)} de {len(ids)} detalhes falharam. "
            "Nenhum arquivo de detalhes foi salvo."
        )

    data_hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nome_arquivo = f"estabelecimentos_detalhe_recife_{data_hoje}.json"
    salvar_json(detalhes, nome_arquivo)

    print("Concluído!")
    