"""Classificador demonstrativo de risco de campos sem resposta registrada."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

COLUNAS_CATEGORICAS = [
    "profissional_tipo",
    "tipo_atendimento",
    "distrito_sanitario_codigo",
    "turno_atendimento",
]
COLUNA_HISTORICO = "completude_equipe_ultimos_3_meses"
COLUNAS_FEATURES = [COLUNA_HISTORICO, *COLUNAS_CATEGORICAS]

CAMPOS_MONITORADOS = {
    "Raça/Cor": ("raca_cor", None),
    "Deficiência": ("deficiencia_tipo", None),
    "Identidade de Gênero": (
        "identidade_genero",
        "deseja_informar_identidade_genero",
    ),
    "Orientação Sexual": (
        "orientacao_sexual",
        "deseja_informar_orientacao_sexual",
    ),
}

COLUNAS_FEATURES_OBRIGATORIAS = {
    "codigo_equipe",
    "data_atendimento",
    "tipo_atendimento",
    "profissional_tipo",
    "distrito_sanitario_codigo",
    "turno_atendimento",
    "idade",
}


def _criar_alvo(dados: pd.DataFrame, campo: str) -> pd.Series:
    coluna, coluna_status = CAMPOS_MONITORADOS[campo]
    sem_valor = dados[coluna].isna()

    if coluna_status is None:
        return sem_valor.astype("int8")

    status = dados[coluna_status].astype("string").str.strip().str.casefold()
    status_desconhecido = status.notna() & ~status.isin(["sim", "não"])
    if status_desconhecido.any():
        valores = sorted(status[status_desconhecido].dropna().unique().tolist())
        raise ValueError(
            f"Valores inesperados em {coluna_status}: {', '.join(valores)}."
        )

    # "Não" é uma resposta válida; ausência de informação não significa recusa.
    sem_resposta = status.isna() | ((status == "sim") & sem_valor)
    return sem_resposta.astype("int8")


def _adicionar_historico_completude(dados: pd.DataFrame) -> pd.DataFrame:
    resultado = dados.copy()
    resultado["mes"] = resultado["data_atendimento"].dt.to_period("M")
    resultado[COLUNA_HISTORICO] = float("nan")

    meses = sorted(resultado["mes"].dropna().unique())
    mensais = (
        resultado.groupby(["codigo_equipe", "mes"], observed=True)["completo"]
        .mean()
        .rename("completude")
        .reset_index()
    )

    for indice, mes in enumerate(meses):
        meses_anteriores = meses[max(0, indice - 3):indice]
        if not meses_anteriores:
            continue
        historico = (
            mensais[mensais["mes"].isin(meses_anteriores)]
            .groupby("codigo_equipe", observed=True)["completude"]
            .mean()
        )
        mascara_mes = resultado["mes"] == mes
        resultado.loc[mascara_mes, COLUNA_HISTORICO] = (
            resultado.loc[mascara_mes, "codigo_equipe"].map(historico)
        )

    return resultado


def preparar_base(atendimentos: pd.DataFrame, campo: str) -> pd.DataFrame:
    """Cria alvo e features sem usar o valor sensível como variável de entrada."""
    if campo not in CAMPOS_MONITORADOS:
        raise ValueError(f"Campo monitorado não suportado: {campo}.")

    coluna_alvo, coluna_status = CAMPOS_MONITORADOS[campo]
    colunas_obrigatorias = COLUNAS_FEATURES_OBRIGATORIAS | {coluna_alvo}
    if coluna_status is not None:
        colunas_obrigatorias.add(coluna_status)
    faltantes = sorted(colunas_obrigatorias - set(atendimentos.columns))
    if faltantes:
        raise ValueError(
            "A tabela de atendimentos não possui as colunas necessárias: "
            + ", ".join(faltantes)
            + ". Atualize o gerador de dados simulados e execute novamente "
            "a carga/transformação para incluir o turno."
        )
    if atendimentos.empty:
        raise ValueError("Não há atendimentos disponíveis para treinar o modelo.")

    dados = atendimentos.copy()
    dados["data_atendimento"] = pd.to_datetime(
        dados["data_atendimento"], errors="coerce"
    )
    dados["idade"] = pd.to_numeric(dados["idade"], errors="coerce")
    dados = dados.dropna(
        subset=[
            "codigo_equipe",
            "data_atendimento",
            "idade",
            "profissional_tipo",
            "tipo_atendimento",
            "distrito_sanitario_codigo",
            "turno_atendimento",
        ]
    ).copy()
    if dados.empty:
        raise ValueError("Não há registros com data e features válidas.")

    if campo in ("Identidade de Gênero", "Orientação Sexual"):
        dados = dados[dados["idade"] >= 10].copy()
    if dados.empty:
        raise ValueError(
            "Não há registros elegíveis para o campo selecionado."
        )

    dados["risco_nao_preenchimento"] = _criar_alvo(dados, campo)
    dados["completo"] = 1 - dados["risco_nao_preenchimento"]
    dados = _adicionar_historico_completude(dados)

    for coluna in COLUNAS_CATEGORICAS:
        dados[coluna] = dados[coluna].astype("string").fillna("Não informado")

    dados = dados.dropna(subset=[COLUNA_HISTORICO]).copy()
    if dados.empty:
        raise ValueError(
            "São necessários registros históricos de pelo menos dois meses "
            "para calcular a completude anterior das equipes."
        )
    return dados.sort_values("data_atendimento").reset_index(drop=True)


def _criar_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("historico", StandardScaler(), [COLUNA_HISTORICO]),
            (
                "categorias",
                OneHotEncoder(handle_unknown="ignore"),
                COLUNAS_CATEGORICAS,
            ),
        ],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            ("preprocessamento", preprocessor),
            (
                "classificador",
                LogisticRegression(max_iter=1000, random_state=42),
            ),
        ]
    )


def _avaliar_modelo(
    pipeline: Pipeline,
    teste: pd.DataFrame,
) -> dict[str, Any]:
    y_teste = teste["risco_nao_preenchimento"]
    probabilidades = pipeline.predict_proba(teste[COLUNAS_FEATURES])[:, 1]
    previsoes = (probabilidades >= 0.5).astype("int8")
    metricas = {
        "acuracia": float(accuracy_score(y_teste, previsoes)),
        "precisao": float(
            precision_score(y_teste, previsoes, zero_division=0)
        ),
        "recall": float(recall_score(y_teste, previsoes, zero_division=0)),
        "roc_auc": (
            float(roc_auc_score(y_teste, probabilidades))
            if y_teste.nunique() == 2
            else None
        ),
        "n_treino": 0,
        "n_teste": int(len(teste)),
        "mes_inicio_teste": str(teste["mes"].min()),
        "mes_fim_teste": str(teste["mes"].max()),
    }
    return metricas


def treinar_e_prever(atendimentos: pd.DataFrame, campo: str) -> dict[str, Any]:
    """Avalia temporalmente e gera riscos para o próximo mês de cada equipe."""
    dados = preparar_base(atendimentos, campo)
    meses = sorted(dados["mes"].unique())
    if len(meses) < 4:
        raise ValueError(
            "São necessários ao menos quatro meses de dados elegíveis para "
            "uma validação temporal."
        )

    meses_treino = meses[-4:-1]
    meses_teste = meses[-1:]
    treino = dados[dados["mes"].isin(meses_treino)]
    teste = dados[dados["mes"].isin(meses_teste)]

    if treino["risco_nao_preenchimento"].nunique() < 2:
        raise ValueError(
            "O período de treino precisa conter registros preenchidos e "
            "sem resposta para o campo selecionado."
        )
    if teste["risco_nao_preenchimento"].nunique() < 2:
        raise ValueError(
            "O período de validação precisa conter registros preenchidos e "
            "sem resposta para o campo selecionado."
        )

    modelo_validacao = _criar_pipeline()
    modelo_validacao.fit(treino[COLUNAS_FEATURES], treino["risco_nao_preenchimento"])
    metricas = _avaliar_modelo(modelo_validacao, teste)
    metricas["n_treino"] = int(len(treino))
    metricas["mes_inicio_treino"] = str(treino["mes"].min())
    metricas["mes_fim_treino"] = str(treino["mes"].max())

    modelo_final = _criar_pipeline()
    janela_recente = dados[dados["mes"].isin(meses[-3:])]
    modelo_final.fit(
        janela_recente[COLUNAS_FEATURES],
        janela_recente["risco_nao_preenchimento"],
    )

    meses_recentes = meses[-3:]
    completude_recente = (
        dados[dados["mes"].isin(meses_recentes)]
        .groupby("codigo_equipe", observed=True)["completo"]
        .mean()
    )
    referencia = dados[dados["mes"] == meses[-1]].copy()
    referencia[COLUNA_HISTORICO] = referencia["codigo_equipe"].map(
        completude_recente
    )
    referencia["risco_previsto"] = modelo_final.predict_proba(
        referencia[COLUNAS_FEATURES]
    )[:, 1]
    ranking = (
        referencia.groupby(
            ["codigo_equipe", "distrito_sanitario_codigo"], observed=True
        )
        .agg(
            risco_previsto=("risco_previsto", "mean"),
            atendimentos_referencia=("risco_previsto", "size"),
        )
        .reset_index()
        .sort_values("risco_previsto", ascending=False)
        .reset_index(drop=True)
    )
    ranking["risco_previsto"] = ranking["risco_previsto"].clip(0, 1)

    nomes_features = modelo_final.named_steps[
        "preprocessamento"
    ].get_feature_names_out()
    coeficientes = modelo_final.named_steps["classificador"].coef_[0]
    importancia = {}
    for nome, coeficiente in zip(nomes_features, coeficientes):
        nome_transformado = nome.split("__", maxsplit=1)[-1]
        grupo = (
            "Histórico da equipe"
            if nome_transformado == COLUNA_HISTORICO
            else next(
                (
                    coluna.replace("_", " ").capitalize()
                    for coluna in COLUNAS_CATEGORICAS
                    if nome_transformado.startswith(f"{coluna}_")
                ),
                nome_transformado,
            )
        )
        importancia[grupo] = importancia.get(grupo, 0.0) + abs(float(coeficiente))
    total_importancia = sum(importancia.values())
    if total_importancia:
        importancia = {
            nome: valor / total_importancia
            for nome, valor in importancia.items()
        }

    return {
        "modelo": modelo_final,
        "metricas": metricas,
        "ranking": ranking,
        "importancia": importancia,
        "total_atendimentos": int(len(atendimentos)),
        "total_elegivel": int(len(dados)),
        "mes_referencia": str(meses[-1]),
        "meses_teste": [str(mes) for mes in meses_teste],
    }
