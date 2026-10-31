import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")


def testar_conexao():
    if not NEON_DATABASE_URL:
        raise SystemExit(
            "Configure NEON_DATABASE_URL no arquivo .env para acessar o Neon."
        )

    engine = create_engine(NEON_DATABASE_URL)
    with engine.connect() as conexao:
        resultado = conexao.execute(text("SELECT version();"))
        versao = resultado.scalar()
        print("Conexão com o Neon (Postgres) funcionou!")
        print(f"Versão do Postgres: {versao}")


if __name__ == "__main__":
    testar_conexao()
