import unittest
from pathlib import Path
import re

from sqlalchemy import create_engine, text

from src.dashboard.pagina_dados import (
    CONSULTAS,
    CONSULTAS_AVANCADAS,
    TABELAS_CONSULTAVEIS,
    atualizar_atendimento,
    atualizar_referencia_distrito,
    excluir_atendimento,
    excluir_referencia_distrito,
    inserir_atendimento,
    inserir_referencia_distrito,
    montar_sql_consulta_tabela,
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

    def test_disponibiliza_consultas_e_visoes_da_etapa_quatro(self):
        self.assertEqual(len(CONSULTAS_AVANCADAS), 4)
        consultas = list(CONSULTAS_AVANCADAS.values())
        self.assertIn("LEFT JOIN", consultas[0]["sql"].upper())
        self.assertIn("IS NULL", consultas[0]["sql"].upper())
        self.assertIn("FULL OUTER JOIN", consultas[1]["sql"].upper())
        self.assertIn("SELECT AVG(", consultas[2]["sql"].upper())
        self.assertIn("SELECT 1.0 * COUNT(", consultas[3]["sql"].upper())
        self.assertIn(
            "vw_equidade_distrital",
            {tabela for tabela, _ in TABELAS_CONSULTAVEIS.values()},
        )
        self.assertIn(
            "vw_completude_por_equipe",
            {tabela for tabela, _ in TABELAS_CONSULTAVEIS.values()},
        )

    def test_entregavel_sql_contem_indices_consultas_e_visoes_exigidos(self):
        raiz = Path(__file__).resolve().parents[1]
        sql = (raiz / "Etapa_04_Consultas_Avancadas.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("idx_mock_atendimentos_equipe_data_etapa04", sql)
        self.assertIn("idx_mock_atendimentos_data_distrito_etapa04", sql)

        consultas = re.findall(r"-- CONSULTA \d+ -", sql)
        self.assertEqual(len(consultas), 4)
        self.assertIn("LEFT JOIN", sql.upper())
        self.assertIn("IS NULL", sql.upper())
        self.assertIn("FULL OUTER JOIN", sql.upper())
        self.assertGreaterEqual(
            len(re.findall(r"\bSELECT\b", sql[sql.index("-- CONSULTA 3"):].upper())),
            4,
        )

        visao_distrital = sql.split(
            "CREATE OR REPLACE VIEW vw_equidade_distrital AS", 1
        )[1].split("COMMENT ON VIEW vw_equidade_distrital", 1)[0]
        visao_equipe = sql.split(
            "CREATE OR REPLACE VIEW vw_completude_por_equipe AS", 1
        )[1].split("COMMENT ON VIEW vw_completude_por_equipe", 1)[0]
        self.assertGreaterEqual(
            len(re.findall(r"\b(?:LEFT|FULL|INNER)?\s*JOIN\b", visao_distrital, re.I)),
            3,
        )
        self.assertGreaterEqual(
            len(re.findall(r"\b(?:LEFT|FULL|INNER)?\s*JOIN\b", visao_equipe, re.I)),
            3,
        )

    def test_consulta_tabela_usa_lista_permitida_e_paginacao_parametrizada(self):
        tabela, chave = TABELAS_CONSULTAVEIS["Atendimentos simulados"]
        sql = montar_sql_consulta_tabela(tabela, limite=25, deslocamento=50)

        self.assertIn(f'SELECT * FROM "{tabela}"', sql)
        self.assertIn(f'ORDER BY "{chave}"', sql)
        self.assertIn("LIMIT :limite OFFSET :deslocamento", sql)
        self.assertEqual(len(TABELAS_CONSULTAVEIS), 8)

    def test_consulta_tabela_rejeita_identificador_nao_permitido(self):
        with self.assertRaisesRegex(ValueError, "lista permitida"):
            montar_sql_consulta_tabela("mock_pec_atendimentos; DROP TABLE", 25, 0)

    def test_consulta_tabela_valida_limite_e_deslocamento(self):
        with self.assertRaisesRegex(ValueError, "limite"):
            montar_sql_consulta_tabela("mock_pec_atendimentos", 501, 0)
        with self.assertRaisesRegex(ValueError, "deslocamento"):
            montar_sql_consulta_tabela("mock_pec_atendimentos", 25, -1)

    def test_consulta_tabela_retorna_pagina_de_registros(self):
        with self.engine.begin() as conexao:
            conexao.execute(
                text("""
                    INSERT INTO mock_pec_atendimentos (
                        id_atendimento, distrito_sanitario_codigo
                    ) VALUES
                        (1, '01'),
                        (2, '02'),
                        (3, '03')
                """)
            )

        sql = montar_sql_consulta_tabela("mock_pec_atendimentos", 2, 1)
        with self.engine.connect() as conexao:
            resultado = conexao.execute(
                text(sql),
                {"limite": 2, "deslocamento": 1},
            ).mappings().all()

        self.assertEqual(
            [registro["id_atendimento"] for registro in resultado],
            [2, 3],
        )


if __name__ == "__main__":
    unittest.main()
