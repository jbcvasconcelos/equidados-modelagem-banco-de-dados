import os

from dotenv import load_dotenv
from pymongo import MongoClient
from sqlalchemy import create_engine, text

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")
NOME_BANCO_MONGO = "bronze_equidade_saude"

DDL_TABELAS = """
CREATE TABLE IF NOT EXISTS unidades_saude (
    cnes                    TEXT PRIMARY KEY,
    nome_fantasia           TEXT,
    nome_empresarial        TEXT,
    bairro                  TEXT,
    distrito_sanitario_codigo TEXT,
    distrito_sanitario_nome TEXT,
    endereco                TEXT,
    cep                     TEXT,
    latitude                DOUBLE PRECISION,
    longitude               DOUBLE PRECISION,
    tipo_estabelecimento    TEXT
);

CREATE TABLE IF NOT EXISTS equipes_saude (
    codigo_equipe   TEXT PRIMARY KEY,
    nome_equipe     TEXT,
    tipo_equipe     TEXT,
    cnes_unidade    TEXT REFERENCES unidades_saude(cnes),
    data_ativacao   TEXT,
    data_desativacao TEXT
);

CREATE TABLE IF NOT EXISTS censo_raca_cor (
    raca_cor    TEXT PRIMARY KEY,
    populacao   BIGINT,
    ano         INTEGER
);

CREATE TABLE IF NOT EXISTS censo_deficiencia (
    tipo_dificuldade    TEXT PRIMARY KEY,
    populacao           BIGINT,
    ano                 INTEGER,
    e_total             BOOLEAN NOT NULL DEFAULT FALSE
);
"""


def criar_tabelas(engine):
    with engine.begin() as conexao:
        conexao.execute(text(DDL_TABELAS))
    print("Tabelas criadas.")


def transformar_unidades_saude(colecao):
    linhas = []
    for doc in colecao.find():
        linhas.append({
            "cnes": doc.get("cnes"),
            "nome_fantasia": doc.get("noFantasia"),
            "nome_empresarial": doc.get("noEmpresarial"),
            "bairro": doc.get("bairro"),
            "distrito_sanitario_codigo": doc.get("coDistritoSanitario"),
            "distrito_sanitario_nome": doc.get("dsDistrito"),
            "endereco": doc.get("noLogradouro"),
            "cep": doc.get("cep"),
            "latitude": float(doc["nuLatitude"]) if doc.get("nuLatitude") else None,
            "longitude": float(doc["nuLongitude"]) if doc.get("nuLongitude") else None,
            "tipo_estabelecimento": doc.get("dsTipoEstabelecimento"),
        })
    return linhas


def transformar_equipes_saude(colecao):
    linhas = []
    for doc in colecao.find():
        linhas.append({
            "codigo_equipe": doc.get("coEquipe"),
            "nome_equipe": doc.get("nomeEquipe"),
            "tipo_equipe": doc.get("dsEquipe"),
            "cnes_unidade": doc.get("_cnes_unidade"),
            "data_ativacao": doc.get("dtAtivacao"),
            "data_desativacao": doc.get("dtDesativacao"),
        })
    return linhas


def transformar_censo_raca_cor(colecao):
    linhas = []
    for doc in colecao.find():
        if doc.get("NC") == "Nível Territorial (Código)":
            continue  # linha de cabeçalho da API SIDRA, não é dado
        if doc.get("D4N") == "Total":
            continue  # a linha "Total" não é uma categoria de raça/cor, pulamos
        linhas.append({
            "raca_cor": doc.get("D4N"),
            "populacao": int(doc.get("V")),
            "ano": int(doc.get("D3N")),
        })
    return linhas


def transformar_censo_deficiencia(colecao):
    linhas = []
    for doc in colecao.find():
        if doc.get("NC") == "Nível Territorial (Código)":
            continue  # linha de cabeçalho da API SIDRA, não é dado
        if doc.get("D2N") != "Pessoas de 2 anos ou mais de idade com deficiência":
            continue
        # as categorias não são mutuamente exclusivas (uma pessoa pode ter mais
        # de um tipo de dificuldade), por isso guardamos o "Total" oficial
        # como uma linha marcada, em vez de deixar quem consome a tabela somar
        # as categorias e chegar num número inflado.
        linhas.append({
            "tipo_dificuldade": doc.get("D4N"),
            "populacao": int(doc.get("V")),
            "ano": int(doc.get("D3N")),
            "e_total": doc.get("D4N") == "Total",
        })
    return linhas


def inserir_linhas(engine, tabela, linhas):
    if not linhas:
        print(f"  nenhuma linha para inserir em '{tabela}'")
        return
    colunas = list(linhas[0].keys())
    placeholders = ", ".join(f":{c}" for c in colunas)
    atualizacoes = ", ".join(
        f"{coluna} = EXCLUDED.{coluna}" for coluna in colunas[1:]
    )
    sql = text(
        f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({placeholders}) "
        f"ON CONFLICT ({colunas[0]}) DO UPDATE SET {atualizacoes}"
    )
    with engine.begin() as conexao:
        conexao.execute(sql, linhas)
    print(f"  {len(linhas)} linha(s) inserida(s) em '{tabela}'")


if __name__ == "__main__":
    if not MONGO_URI:
        raise SystemExit("Configure MONGO_URI no arquivo .env para acessar o MongoDB.")
    if not NEON_DATABASE_URL:
        raise SystemExit(
            "Configure NEON_DATABASE_URL no arquivo .env para acessar o Neon."
        )

    cliente_mongo = MongoClient(MONGO_URI)
    banco_mongo = cliente_mongo[NOME_BANCO_MONGO]

    engine_neon = create_engine(NEON_DATABASE_URL)

    criar_tabelas(engine_neon)

    print("Transformando unidades_saude...")
    inserir_linhas(
        engine_neon,
        "unidades_saude",
        transformar_unidades_saude(banco_mongo["cnes_estabelecimentos_detalhe"]),
    )

    print("Transformando equipes_saude...")
    inserir_linhas(
        engine_neon,
        "equipes_saude",
        transformar_equipes_saude(banco_mongo["cnes_equipes"]),
    )

    print("Transformando censo_raca_cor...")
    inserir_linhas(
        engine_neon,
        "censo_raca_cor",
        transformar_censo_raca_cor(banco_mongo["ibge_censo_raca_cor"]),
    )

    print("Transformando censo_deficiencia...")
    inserir_linhas(
        engine_neon,
        "censo_deficiencia",
        transformar_censo_deficiencia(banco_mongo["ibge_censo_deficiencia_tipo"]),
    )

    print("\nConcluído!")
