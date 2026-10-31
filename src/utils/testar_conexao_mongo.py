import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")


def testar_conexao():
    if not MONGO_URI:
        raise SystemExit("Configure MONGO_URI no arquivo .env para acessar o MongoDB.")

    cliente = MongoClient(MONGO_URI)
    cliente.admin.command("ping")
    print("Conexão com o MongoDB Atlas funcionou!")
    print("Bancos de dados existentes:", cliente.list_database_names())


if __name__ == "__main__":
    testar_conexao()
