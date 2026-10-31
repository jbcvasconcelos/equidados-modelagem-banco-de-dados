import unittest

from sqlalchemy import create_engine, text

from src.dashboard.pagina_dados import (
    CONSULTAS,
    atualizar_atendimento,
    atualizar_referencia_distrito,
    excluir_atendimento,
    excluir_referencia_distrito,
    inserir_atendimento,
    inserir_referencia_distrito,
)


class PaginaDadosTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        with self.engine.begin() as conexao:
            conexao.execute(text("""
                CREATE TABLE mock_pec_atendimentos (
                    id_atendimento INTEGER PRIMARY KEY,
                    codigo_equipe TEXT,
                    cnes_unidade TEXT,
                    distrito_sanitario_codigo TEXT,
                    data_atendimento DATE,
                    tipo_atendimento TEXT,
                    profissional_tipo TEXT,
                    turno_atendimento TEXT,
                    idade INTEGER,
                    raca_cor TEXT,
                    deficiencia_tipo TEXT,
                    deseja_informar_orientacao_sexual TEXT,
                    orientacao_sexual TEXT,
                    deseja_informar_identidade_genero TEXT,
                    identidade_genero TEXT,
                    nome_social TEXT
                )
            """))
            conexao.execute(text("""
                CREATE TABLE mock_populacao_negra_distrito (
                    distrito_sanitario_codigo TEXT PRIMARY KEY,
                    populacao_negra_pct_esperado NUMERIC
                )
            """))

    def tearDown(self):
        self.engine.dispose()

    def test_crud_atendimento(self):
        dados = {
            "id_atendimento": 1,
            "codigo_equipe": None,
            "cnes_unidade": None,
            "distrito_sanitario_codigo": "01",
            "data_atendimento": "2026-10-31",
            "tipo_atendimento": "Consulta",
            "profissional_tipo": "ACS",
            "turno_atendimento": "Manhã",
            "idade": 30,
            "raca_cor": "Parda",
            "deficiencia_tipo": "Nenhuma",
            "deseja_informar_orientacao_sexual": None,
            "orientacao_sexual": None,
            "deseja_informar_identidade_genero": None,
            "identidade_genero": None,
            "nome_social": None,
        }

        inserir_atendimento(self.engine, dados)
        atualizados = {**dados, "tipo_atendimento": "Retorno"}
        self.assertEqual(
            atualizar_atendimento(self.engine, 1, atualizados),
            1,
        )
        with self.engine.connect() as conexao:
            tipo = conexao.execute(
                text("""
                    SELECT tipo_atendimento FROM mock_pec_atendimentos
                    WHERE id_atendimento = 1
                """)
            ).scalar_one()
        self.assertEqual(tipo, "Retorno")
        self.assertEqual(excluir_atendimento(self.engine, 1), 1)
        self.assertEqual(excluir_atendimento(self.engine, 1), 0)

    def test_crud_referencia_distrital(self):
        inserir_referencia_distrito(self.engine, "01", 0.608)
        self.assertEqual(
            atualizar_referencia_distrito(self.engine, "01", 0.61),
            1,
        )
        with self.engine.connect() as conexao:
            percentual = conexao.execute(
                text("""
                    SELECT populacao_negra_pct_esperado
                    FROM mock_populacao_negra_distrito
                    WHERE distrito_sanitario_codigo = '01'
                """)
            ).scalar_one()
        self.assertAlmostEqual(float(percentual), 0.61)
        self.assertEqual(excluir_referencia_distrito(self.engine, "01"), 1)
        self.assertEqual(excluir_referencia_distrito(self.engine, "01"), 0)

    def test_disponibiliza_quatro_consultas_incluindo_join(self):
        self.assertEqual(len(CONSULTAS), 4)
        consultas_com_join = [
            definicao for definicao in CONSULTAS.values()
            if "JOIN" in definicao["sql"].upper()
        ]
        self.assertGreaterEqual(len(consultas_com_join), 1)


if __name__ == "__main__":
    unittest.main()
