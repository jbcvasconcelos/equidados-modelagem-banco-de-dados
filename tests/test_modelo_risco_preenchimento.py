import unittest

import pandas as pd

from src.ml.modelo_risco_preenchimento import (
    COLUNAS_FEATURES,
    preparar_base,
    treinar_e_prever,
)


def criar_atendimentos(meses=6):
    linhas = []
    identificador = 1
    for indice_mes in range(meses):
        mes = indice_mes + 1
        for indice_equipe, equipe in enumerate(("EQ01", "EQ02")):
            for indice in range(30):
                sem_raca = (indice + indice_mes + indice_equipe) % 4 == 0
                linhas.append(
                    {
                        "id_atendimento": identificador,
                        "codigo_equipe": equipe,
                        "distrito_sanitario_codigo": (
                            "01" if indice_equipe == 0 else "02"
                        ),
                        "data_atendimento": f"2026-{mes:02d}-{indice % 27 + 1:02d}",
                        "tipo_atendimento": (
                            "Primeira consulta" if indice % 2 else "Retorno"
                        ),
                        "profissional_tipo": (
                            "ACS" if indice % 3 else "Enfermeiro"
                        ),
                        "turno_atendimento": (
                            "Manhã" if indice % 2 else "Tarde"
                        ),
                        "idade": 30,
                        "raca_cor": None if sem_raca else "Parda",
                        "deficiencia_tipo": "Nenhuma",
                        "deseja_informar_orientacao_sexual": (
                            "Não" if indice % 3 == 0 else "Sim"
                        ),
                        "orientacao_sexual": (
                            None if indice % 3 == 0 else "Heterossexual"
                        ),
                        "deseja_informar_identidade_genero": (
                            "Não" if indice % 3 == 0 else "Sim"
                        ),
                        "identidade_genero": (
                            None if indice % 3 == 0 else "Mulher cisgênero"
                        ),
                    }
                )
                identificador += 1
    return pd.DataFrame(linhas)


class ModeloRiscoPreenchimentoTests(unittest.TestCase):
    def test_historico_usa_apenas_meses_anteriores(self):
        atendimentos = criar_atendimentos(meses=3)
        base = preparar_base(atendimentos, "Raça/Cor")

        janeiro = base[base["mes"] == pd.Period("2026-01", freq="M")]
        fevereiro = base[base["mes"] == pd.Period("2026-02", freq="M")]

        self.assertTrue(janeiro.empty)
        historico_janeiro = (
            atendimentos[atendimentos["data_atendimento"].str.startswith("2026-01")]
            .groupby("codigo_equipe")["raca_cor"]
            .apply(lambda valores: valores.notna().mean())
        )
        for equipe, grupo in fevereiro.groupby("codigo_equipe"):
            self.assertTrue(
                (
                    grupo["completude_equipe_ultimos_3_meses"]
                    == historico_janeiro[equipe]
                ).all()
            )
        self.assertEqual(
            set(COLUNAS_FEATURES),
            {
                "completude_equipe_ultimos_3_meses",
                "profissional_tipo",
                "tipo_atendimento",
                "distrito_sanitario_codigo",
                "turno_atendimento",
            },
        )

    def test_recusa_informada_nao_e_rotulada_como_campo_em_branco(self):
        atendimentos = criar_atendimentos(meses=4)
        base = preparar_base(atendimentos, "Orientação Sexual")
        recusa = base["deseja_informar_orientacao_sexual"] == "Não"

        self.assertTrue(recusa.any())
        self.assertEqual(base.loc[recusa, "risco_nao_preenchimento"].sum(), 0)

    def test_schema_antigo_sem_turno_falha_com_mensagem_clara(self):
        atendimentos = criar_atendimentos(meses=4).drop(
            columns=["turno_atendimento"]
        )

        with self.assertRaisesRegex(ValueError, "turno_atendimento"):
            preparar_base(atendimentos, "Raça/Cor")

    def test_carrega_somente_o_alvo_sensivel_escolhido(self):
        atendimentos = criar_atendimentos(meses=4).drop(
            columns=[
                "deficiencia_tipo",
                "deseja_informar_orientacao_sexual",
                "orientacao_sexual",
                "deseja_informar_identidade_genero",
                "identidade_genero",
            ]
        )

        base = preparar_base(atendimentos, "Raça/Cor")

        self.assertIn("raca_cor", base.columns)
        self.assertNotIn("identidade_genero", base.columns)

    def test_modelo_faz_validacao_temporal_e_ranking_por_equipe(self):
        resultado = treinar_e_prever(
            criar_atendimentos(meses=6),
            "Raça/Cor",
        )

        self.assertGreater(resultado["metricas"]["n_treino"], 0)
        self.assertGreater(resultado["metricas"]["n_teste"], 0)
        self.assertIsNotNone(resultado["metricas"]["roc_auc"])
        self.assertEqual(set(resultado["ranking"]["codigo_equipe"]), {"EQ01", "EQ02"})
        self.assertTrue(
            resultado["ranking"]["risco_previsto"].between(0, 1).all()
        )


if __name__ == "__main__":
    unittest.main()
