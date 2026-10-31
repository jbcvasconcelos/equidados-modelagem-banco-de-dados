"""
Transforma os dados FICTÍCIOS/SIMULADOS de camada bronze (MongoDB) em tabelas
relacionais na camada silver (Neon/PostgreSQL).

Não representa pacientes, atendimentos ou população real de Recife — ver aviso
nas próprias tabelas (COMMENT ON TABLE) e nos documentos de origem (_meta.aviso).
"""

import os

from dotenv import load_dotenv
from pymongo import MongoClient
from sqlalchemy import create_engine, text

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")
NOME_BANCO_MONGO = "bronze_equidade_saude"

DDL_TABELAS = """
CREATE TABLE IF NOT EXISTS mock_pec_atendimentos (
    id_atendimento                      INTEGER PRIMARY KEY,
    codigo_equipe                       TEXT REFERENCES equipes_saude(codigo_equipe),
    cnes_unidade                         TEXT REFERENCES unidades_saude(cnes),
    distrito_sanitario_codigo            TEXT,
    data_atendimento                    DATE,
    tipo_atendimento                    TEXT,
    profissional_tipo                   TEXT,
    turno_atendimento                   TEXT,
    idade                                INTEGER,
    raca_cor                            TEXT,
    deficiencia_tipo                    TEXT,
    deseja_informar_orientacao_sexual   TEXT,
    orientacao_sexual                   TEXT,
    deseja_informar_identidade_genero   TEXT,
    identidade_genero                   TEXT,
    nome_social                         TEXT
);
ALTER TABLE mock_pec_atendimentos
    ADD COLUMN IF NOT EXISTS turno_atendimento TEXT;
COMMENT ON TABLE mock_pec_atendimentos IS
    'DADOS FICTICIOS/SIMULADOS -- nao representam pacientes ou atendimentos '
    'reais. Gerados para testar o pipeline enquanto o acesso ao PEC/e-SUS real '
    'nao e liberado pela Secretaria.';

CREATE TABLE IF NOT EXISTS mock_populacao_negra_distrito (
    distrito_sanitario_codigo      TEXT PRIMARY KEY,
    populacao_negra_pct_esperado   NUMERIC
);
COMMENT ON TABLE mock_populacao_negra_distrito IS
    'DADOS FICTICIOS/SIMULADOS -- distribuicao ilustrativa da populacao negra '
    'por Distrito Sanitario, usada como referencia ("esperado") para comparar '
    'com o observado em mock_pec_atendimentos. Nao representa a distribuicao '
    'real de Recife.';
"""


def criar_tabelas(engine):
    with engine.begin() as conexao:
        conexao.execute(text(DDL_TABELAS))
    print("Tabelas mock criadas.")


def transformar_mock_atendimentos(colecao):
    linhas = []
    for doc in colecao.find():
        linhas.append({
            "id_atendimento": doc.get("id_atendimento"),
            "codigo_equipe": doc.get("codigo_equipe"),
            "cnes_unidade": doc.get("cnes_unidade"),
            "distrito_sanitario_codigo": doc.get("distrito_sanitario_codigo"),
            "data_atendimento": doc.get("data_atendimento"),
            "tipo_atendimento": doc.get("tipo_atendimento"),
            "profissional_tipo": doc.get("profissional_tipo"),
            "turno_atendimento": doc.get("turno_atendimento"),
            "idade": doc.get("idade"),
            "raca_cor": doc.get("raca_cor"),
            "deficiencia_tipo": doc.get("deficiencia_tipo"),
            "deseja_informar_orientacao_sexual": doc.get("deseja_informar_orientacao_sexual"),
            "orientacao_sexual": doc.get("orientacao_sexual"),
            "deseja_informar_identidade_genero": doc.get("deseja_informar_identidade_genero"),
            "identidade_genero": doc.get("identidade_genero"),
            "nome_social": doc.get("nome_social"),
        })
    return linhas


def transformar_mock_populacao_negra_distrito(colecao):
    linhas = []
    for doc in colecao.find():
        linhas.append({
            "distrito_sanitario_codigo": doc.get("distrito_sanitario_codigo"),
            "populacao_negra_pct_esperado": doc.get("populacao_negra_pct_esperado"),
        })
    return linhas


def inserir_linhas(engine, tabela, linhas, tamanho_lote=1000):
    if not linhas:
        print(f"  nenhuma linha para inserir em '{tabela}'")
        return
    colunas = list(linhas[0].keys())
    total_inserido = 0
    with engine.begin() as conexao:
        for inicio in range(0, len(linhas), tamanho_lote):
            lote = linhas[inicio:inicio + tamanho_lote]
            valores_sql = []
            parametros = {}
            for i, linha in enumerate(lote):
                nomes_params = [f"{coluna}_{i}" for coluna in colunas]
                valores_sql.append("(" + ", ".join(f":{n}" for n in nomes_params) + ")")
                for coluna, nome_param in zip(colunas, nomes_params):
                    parametros[nome_param] = linha[coluna]
            atualizacoes = ", ".join(
                f"{coluna} = EXCLUDED.{coluna}" for coluna in colunas[1:]
            )
            sql = text(
                f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES "
                f"{', '.join(valores_sql)} "
                f"ON CONFLICT ({colunas[0]}) DO UPDATE SET {atualizacoes}"
            )
            conexao.execute(sql, parametros)
            total_inserido += len(lote)
    print(f"  {total_inserido} linha(s) inserida(s) em '{tabela}'")


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

    print("Transformando mock_pec_atendimentos...")
    inserir_linhas(
        engine_neon,
        "mock_pec_atendimentos",
        transformar_mock_atendimentos(banco_mongo["mock_pec_atendimentos"]),
    )

    print("Transformando mock_populacao_negra_distrito...")
    inserir_linhas(
        engine_neon,
        "mock_populacao_negra_distrito",
        transformar_mock_populacao_negra_distrito(banco_mongo["mock_populacao_negra_distrito"]),
    )

    print("\nConcluído! Lembre-se: essas duas tabelas contêm dados fictícios/simulados.")
