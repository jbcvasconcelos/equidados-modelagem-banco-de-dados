import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
NOME_BANCO = "bronze_equidade_saude"

PASTA_BRONZE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "bronze")


MAPEAMENTO_ARQUIVO_COLECAO = {
    "estabelecimentos_recife": "cnes_estabelecimentos",
    "estabelecimentos_detalhe_recife": "cnes_estabelecimentos_detalhe",
    "equipes_recife": "cnes_equipes",
    "censo_raca_cor_recife": "ibge_censo_raca_cor",
    "censo_deficiencia_tipo_recife": "ibge_censo_deficiencia_tipo",
    "distritos_sanitarios": "dados_recife_distritos_geometria",
    "distritos_bairros": "dados_recife_distritos_bairros",
    "atendimentos_mock": "mock_pec_atendimentos",
    "populacao_negra_distrito_mock": "mock_populacao_negra_distrito",
}


def identificar_colecao(nome_arquivo):
    for prefixo, colecao in MAPEAMENTO_ARQUIVO_COLECAO.items():
        if nome_arquivo.startswith(prefixo):
            return colecao
    return None


def carregar_arquivo_json(caminho):
    with open(caminho, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def inserir_no_mongo(banco, colecao, dados, nome_arquivo):
    agora = datetime.now(timezone.utc).isoformat()

    # Um GeoJSON vem como um único dicionário (FeatureCollection), não uma lista.
    # Guardamos ele como um documento só, mantendo a estrutura original.
    if isinstance(dados, dict):
        documentos = [dados]
    else:
        documentos = dados

    if not documentos:
        raise ValueError(
            f"Arquivo '{nome_arquivo}' não contém documentos; "
            f"a coleção '{colecao}' não será apagada."
        )

    for documento in documentos:
        documento["_meta"] = {
            "arquivo_origem": nome_arquivo,
            "carregado_em": agora,
        }
        if colecao.startswith("mock_"):
            documento["_meta"]["aviso"] = "SIMULADO — não representa dados reais"

    banco[colecao].delete_many({})  # limpa a coleção antes de recarregar
    if documentos:
        banco[colecao].insert_many(documentos)

    print(f"  {len(documentos)} documento(s) inserido(s) em '{colecao}'")


if __name__ == "__main__":
    if not MONGO_URI:
        raise SystemExit("Configure MONGO_URI no arquivo .env para acessar o MongoDB.")

    cliente = MongoClient(MONGO_URI)
    banco = cliente[NOME_BANCO]

    for pasta_atual, _, arquivos in os.walk(PASTA_BRONZE):
        for nome_arquivo in sorted(arquivos):
            if not nome_arquivo.endswith(".json"):
                continue

            colecao = identificar_colecao(nome_arquivo)
            if colecao is None:
                print(f"Aviso: nenhum mapeamento encontrado para '{nome_arquivo}', pulando")
                continue

            caminho_completo = os.path.join(pasta_atual, nome_arquivo)
            print(f"Carregando '{nome_arquivo}' -> coleção '{colecao}'")

            dados = carregar_arquivo_json(caminho_completo)
            inserir_no_mongo(banco, colecao, dados, nome_arquivo)

    print("\nConcluído! Coleções no banco:", banco.list_collection_names())
