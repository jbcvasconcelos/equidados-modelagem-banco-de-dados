"""CRUD e consultas SQL explícitas para os dados simulados do EquiDados."""

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


CONSULTAS = {
    "Atendimentos por distrito e raça/cor": {
        "sql": """
            SELECT distrito_sanitario_codigo AS distrito,
                   raca_cor,
                   COUNT(*) AS atendimentos
            FROM mock_pec_atendimentos
            WHERE raca_cor IS NOT NULL
            GROUP BY distrito_sanitario_codigo, raca_cor
            ORDER BY distrito_sanitario_codigo, raca_cor
        """,
        "tipo_grafico": "bar",
        "colunas_numericas": ["atendimentos"],
    },
    "Completude dos campos por mês": {
        "sql": """
            SELECT TO_CHAR(DATE_TRUNC('month', data_atendimento), 'YYYY-MM')
                       AS mes,
                   ROUND(
                       COUNT(raca_cor)::numeric / NULLIF(COUNT(*), 0) * 100,
                       1
                   ) AS raca_cor_pct,
                   ROUND(
                       COUNT(deficiencia_tipo)::numeric
                           / NULLIF(COUNT(*), 0) * 100,
                       1
                   ) AS deficiencia_pct,
                   ROUND(
                       (COUNT(orientacao_sexual)
                           FILTER (WHERE idade >= 10))::numeric
                           / NULLIF(COUNT(*) FILTER (WHERE idade >= 10), 0)
                           * 100,
                       1
                   ) AS orientacao_sexual_pct,
                   ROUND(
                       (COUNT(identidade_genero)
                           FILTER (WHERE idade >= 10))::numeric
                           / NULLIF(COUNT(*) FILTER (WHERE idade >= 10), 0)
                           * 100,
                       1
                   ) AS identidade_genero_pct
            FROM mock_pec_atendimentos
            WHERE data_atendimento IS NOT NULL
            GROUP BY DATE_TRUNC('month', data_atendimento)
            ORDER BY DATE_TRUNC('month', data_atendimento)
        """,
        "tipo_grafico": "line",
        "colunas_numericas": [
            "raca_cor_pct",
            "deficiencia_pct",
            "orientacao_sexual_pct",
            "identidade_genero_pct",
        ],
    },
    "Atendimentos por equipe e unidade (JOIN)": {
        "sql": """
            SELECT u.distrito_sanitario_codigo AS distrito,
                   e.codigo_equipe,
                   COALESCE(u.nome_fantasia, u.nome_empresarial) AS unidade,
                   COUNT(a.id_atendimento) AS atendimentos
            FROM equipes_saude e
            JOIN unidades_saude u ON u.cnes = e.cnes_unidade
            LEFT JOIN mock_pec_atendimentos a
                ON a.codigo_equipe = e.codigo_equipe
            GROUP BY u.distrito_sanitario_codigo, e.codigo_equipe,
                     u.nome_fantasia, u.nome_empresarial
            ORDER BY atendimentos DESC, e.codigo_equipe
            LIMIT 100
        """,
        "tipo_grafico": "bar",
        "colunas_numericas": ["atendimentos"],
    },
    "Diferença entre referência e registros de raça/cor por distrito (JOIN)": {
        "sql": """
            SELECT p.distrito_sanitario_codigo AS distrito,
                   ROUND(p.populacao_negra_pct_esperado * 100, 1)
                       AS percentual_esperado,
                   ROUND(
                       (COUNT(*) FILTER (
                           WHERE a.raca_cor IN ('Preta', 'Parda')
                       ))::numeric
                           / NULLIF(COUNT(a.raca_cor), 0) * 100,
                       1
                   ) AS percentual_observado,
                   ROUND(
                       p.populacao_negra_pct_esperado * 100
                           - (COUNT(*) FILTER (
                               WHERE a.raca_cor IN ('Preta', 'Parda')
                           ))::numeric
                               / NULLIF(COUNT(a.raca_cor), 0) * 100,
                       1
                   ) AS diferenca_pontos_percentuais
            FROM mock_populacao_negra_distrito p
            LEFT JOIN mock_pec_atendimentos a
                ON a.distrito_sanitario_codigo =
                   p.distrito_sanitario_codigo
            GROUP BY p.distrito_sanitario_codigo,
                     p.populacao_negra_pct_esperado
            ORDER BY p.distrito_sanitario_codigo
        """,
        "tipo_grafico": "bar",
        "colunas_numericas": [
            "percentual_esperado",
            "percentual_observado",
            "diferenca_pontos_percentuais",
        ],
    },
}

RACAS_COR = ["Branca", "Preta", "Parda", "Amarela", "Indígena"]
TIPOS_DEFICIENCIA = [
    "Nenhuma",
    "Auditiva",
    "Intelectual/Cognitiva",
    "TEA",
    "Visual",
    "Física",
    "Outra",
]
SIM_NAO = ["Sim", "Não"]
DISTRITOS = [f"{numero:02d}" for numero in range(1, 9)]
NAO_INFORMADO = "Não informado"


def inserir_atendimento(engine, dados):
    with engine.begin() as conexao:
        conexao.execute(
            text("""
                INSERT INTO mock_pec_atendimentos (
                    id_atendimento, codigo_equipe, cnes_unidade,
                    distrito_sanitario_codigo, data_atendimento,
                    tipo_atendimento, profissional_tipo, turno_atendimento,
                    idade, raca_cor, deficiencia_tipo,
                    deseja_informar_orientacao_sexual, orientacao_sexual,
                    deseja_informar_identidade_genero, identidade_genero,
                    nome_social
                ) VALUES (
                    :id_atendimento, :codigo_equipe, :cnes_unidade,
                    :distrito_sanitario_codigo, :data_atendimento,
                    :tipo_atendimento, :profissional_tipo, :turno_atendimento,
                    :idade, :raca_cor, :deficiencia_tipo,
                    :deseja_informar_orientacao_sexual, :orientacao_sexual,
                    :deseja_informar_identidade_genero, :identidade_genero,
                    :nome_social
                )
            """),
            dados,
        )


def atualizar_atendimento(engine, identificador, dados):
    with engine.begin() as conexao:
        resultado = conexao.execute(
            text("""
                UPDATE mock_pec_atendimentos
                SET codigo_equipe = :codigo_equipe,
                    cnes_unidade = :cnes_unidade,
                    distrito_sanitario_codigo = :distrito_sanitario_codigo,
                    data_atendimento = :data_atendimento,
                    tipo_atendimento = :tipo_atendimento,
                    profissional_tipo = :profissional_tipo,
                    turno_atendimento = :turno_atendimento,
                    idade = :idade,
                    raca_cor = :raca_cor,
                    deficiencia_tipo = :deficiencia_tipo,
                    deseja_informar_orientacao_sexual =
                        :deseja_informar_orientacao_sexual,
                    orientacao_sexual = :orientacao_sexual,
                    deseja_informar_identidade_genero =
                        :deseja_informar_identidade_genero,
                    identidade_genero = :identidade_genero,
                    nome_social = :nome_social
                WHERE id_atendimento = :identificador
            """),
            {**dados, "identificador": identificador},
        )
    return resultado.rowcount


def excluir_atendimento(engine, identificador):
    with engine.begin() as conexao:
        resultado = conexao.execute(
            text("""
                DELETE FROM mock_pec_atendimentos
                WHERE id_atendimento = :identificador
            """),
            {"identificador": identificador},
        )
    return resultado.rowcount


def inserir_referencia_distrito(engine, distrito, percentual):
    with engine.begin() as conexao:
        conexao.execute(
            text("""
                INSERT INTO mock_populacao_negra_distrito (
                    distrito_sanitario_codigo, populacao_negra_pct_esperado
                ) VALUES (:distrito, :percentual)
            """),
            {"distrito": distrito, "percentual": percentual},
        )


def atualizar_referencia_distrito(engine, distrito, percentual):
    with engine.begin() as conexao:
        resultado = conexao.execute(
            text("""
                UPDATE mock_populacao_negra_distrito
                SET populacao_negra_pct_esperado = :percentual
                WHERE distrito_sanitario_codigo = :distrito
            """),
            {"distrito": distrito, "percentual": percentual},
        )
    return resultado.rowcount


def excluir_referencia_distrito(engine, distrito):
    with engine.begin() as conexao:
        resultado = conexao.execute(
            text("""
                DELETE FROM mock_populacao_negra_distrito
                WHERE distrito_sanitario_codigo = :distrito
            """),
            {"distrito": distrito},
        )
    return resultado.rowcount


def _opcao_formulario(formulario, rotulo, opcoes, atual, chave):
    opcoes = list(opcoes)
    if atual is not None and atual not in opcoes:
        opcoes.append(atual)
    valores = [NAO_INFORMADO, *opcoes]
    selecionado = atual if atual in opcoes else NAO_INFORMADO
    indice = valores.index(selecionado)
    valor = formulario.selectbox(rotulo, valores, index=indice, key=chave)
    return None if valor == NAO_INFORMADO else valor


def _dados_formulario_atendimento(formulario, identificador, registro, prefixo,
                                  equipes, unidades):
    original = registro or {}
    padrao = pd.Timestamp.today().date()
    data_original = original.get("data_atendimento")
    if data_original is not None and not pd.isna(data_original):
        data_original = pd.Timestamp(data_original).date()
    else:
        data_original = padrao

    dados = {"id_atendimento": identificador}
    primeira_linha = formulario.columns(2)
    dados["codigo_equipe"] = _opcao_formulario(
        primeira_linha[0], "Equipe", equipes, original.get("codigo_equipe"),
        f"{prefixo}_equipe",
    )
    dados["cnes_unidade"] = _opcao_formulario(
        primeira_linha[1], "Unidade (CNES)", unidades,
        original.get("cnes_unidade"), f"{prefixo}_unidade",
    )

    segunda_linha = formulario.columns(2)
    dados["distrito_sanitario_codigo"] = _opcao_formulario(
        segunda_linha[0], "Distrito sanitário", DISTRITOS,
        original.get("distrito_sanitario_codigo"), f"{prefixo}_distrito",
    )
    dados["data_atendimento"] = segunda_linha[1].date_input(
        "Data do atendimento", value=data_original, key=f"{prefixo}_data",
    )

    terceira_linha = formulario.columns(2)
    dados["tipo_atendimento"] = terceira_linha[0].text_input(
        "Tipo de atendimento", value=original.get("tipo_atendimento") or "",
        key=f"{prefixo}_tipo",
    ) or None
    dados["profissional_tipo"] = terceira_linha[1].text_input(
        "Tipo de profissional", value=original.get("profissional_tipo") or "",
        key=f"{prefixo}_profissional",
    ) or None

    quarta_linha = formulario.columns(2)
    dados["turno_atendimento"] = quarta_linha[0].text_input(
        "Turno", value=original.get("turno_atendimento") or "",
        key=f"{prefixo}_turno",
    ) or None
    idade_original = original.get("idade")
    idade_informada = idade_original is not None and not pd.isna(idade_original)
    dados["idade"] = quarta_linha[1].number_input(
        "Idade", min_value=0, max_value=120,
        value=int(idade_original) if idade_informada else 10,
        key=f"{prefixo}_idade",
    )

    quinta_linha = formulario.columns(2)
    dados["raca_cor"] = _opcao_formulario(
        quinta_linha[0], "Raça/cor", RACAS_COR, original.get("raca_cor"),
        f"{prefixo}_raca",
    )
    dados["deficiencia_tipo"] = _opcao_formulario(
        quinta_linha[1], "Deficiência", TIPOS_DEFICIENCIA,
        original.get("deficiencia_tipo"), f"{prefixo}_deficiencia",
    )

    sexta_linha = formulario.columns(2)
    dados["deseja_informar_orientacao_sexual"] = _opcao_formulario(
        sexta_linha[0], "Deseja informar orientação sexual?", SIM_NAO,
        original.get("deseja_informar_orientacao_sexual"),
        f"{prefixo}_deseja_orientacao",
    )
    dados["orientacao_sexual"] = sexta_linha[1].text_input(
        "Orientação sexual", value=original.get("orientacao_sexual") or "",
        key=f"{prefixo}_orientacao",
    ) or None

    setima_linha = formulario.columns(2)
    dados["deseja_informar_identidade_genero"] = _opcao_formulario(
        setima_linha[0], "Deseja informar identidade de gênero?", SIM_NAO,
        original.get("deseja_informar_identidade_genero"),
        f"{prefixo}_deseja_genero",
    )
    dados["identidade_genero"] = setima_linha[1].text_input(
        "Identidade de gênero", value=original.get("identidade_genero") or "",
        key=f"{prefixo}_genero",
    ) or None
    dados["nome_social"] = formulario.text_input(
        "Nome social", value=original.get("nome_social") or "",
        key=f"{prefixo}_nome_social",
    ) or None
    return dados


def _renderizar_crud_atendimentos(consultar, engine):
    st.markdown("#### Atendimentos simulados")
    st.caption(
        "Os registros desta tabela são fictícios. A inclusão usa o próximo ID "
        "disponível; vínculos com equipe e unidade são opcionais."
    )
    equipes = consultar(
        "SELECT codigo_equipe FROM equipes_saude ORDER BY codigo_equipe"
    )["codigo_equipe"].dropna().astype(str).tolist()
    unidades = consultar(
        "SELECT cnes FROM unidades_saude ORDER BY cnes"
    )["cnes"].dropna().astype(str).tolist()
    maximo = consultar(
        "SELECT COALESCE(MAX(id_atendimento), 0) AS ultimo_id "
        "FROM mock_pec_atendimentos"
    )
    proximo_id = int(maximo.iloc[0]["ultimo_id"]) + 1
    registros = consultar("""
        SELECT id_atendimento, data_atendimento, codigo_equipe,
               distrito_sanitario_codigo, raca_cor
        FROM mock_pec_atendimentos
        ORDER BY id_atendimento DESC
        LIMIT 100
    """)
    st.dataframe(registros, width="stretch", hide_index=True)

    inserir_tab, alterar_tab, excluir_tab = st.tabs(
        ["Inserir", "Alterar", "Excluir"]
    )
    with inserir_tab:
        with st.form("form_inserir_atendimento"):
            identificador = st.number_input(
                "ID do atendimento", min_value=1, value=proximo_id, step=1,
                help="Identificador único da tabela.",
            )
            dados = _dados_formulario_atendimento(
                st, int(identificador), None, "novo_atendimento", equipes, unidades,
            )
            enviado = st.form_submit_button("Inserir atendimento")
        if enviado:
            try:
                inserir_atendimento(engine, dados)
            except SQLAlchemyError as erro:
                st.error(f"Não foi possível inserir o atendimento: {erro}")
            else:
                st.success("Atendimento simulado inserido.")
                st.cache_data.clear()

    if registros.empty:
        st.info("Não há atendimentos para alterar ou excluir.")
        return

    ids = registros["id_atendimento"].astype(int).tolist()
    with alterar_tab:
        identificador_edicao = st.selectbox(
            "Atendimento para alterar", ids, key="selecionar_atendimento_edicao",
        )
        registro = consultar(
            "SELECT * FROM mock_pec_atendimentos "
            "WHERE id_atendimento = :id_atendimento",
            {"id_atendimento": identificador_edicao},
        )
        if not registro.empty:
            with st.form("form_alterar_atendimento"):
                dados = _dados_formulario_atendimento(
                    st, int(identificador_edicao), registro.iloc[0].to_dict(),
                    f"editar_atendimento_{identificador_edicao}", equipes, unidades,
                )
                enviado = st.form_submit_button("Salvar alterações")
            if enviado:
                try:
                    linhas = atualizar_atendimento(
                        engine, int(identificador_edicao), dados,
                    )
                except SQLAlchemyError as erro:
                    st.error(f"Não foi possível alterar o atendimento: {erro}")
                else:
                    if linhas:
                        st.success("Atendimento atualizado.")
                        st.cache_data.clear()
                    else:
                        st.warning("O atendimento selecionado não foi encontrado.")

    with excluir_tab:
        identificador_exclusao = st.selectbox(
            "Atendimento para excluir", ids, key="selecionar_atendimento_exclusao",
        )
        with st.form("form_excluir_atendimento"):
            confirmar = st.checkbox(
                "Confirmo a exclusão deste registro fictício.",
                key="confirmar_exclusao_atendimento",
            )
            enviado = st.form_submit_button("Excluir atendimento")
        if enviado:
            if not confirmar:
                st.warning("Confirme a exclusão antes de continuar.")
            else:
                try:
                    linhas = excluir_atendimento(
                        engine, int(identificador_exclusao),
                    )
                except SQLAlchemyError as erro:
                    st.error(f"Não foi possível excluir o atendimento: {erro}")
                else:
                    if linhas:
                        st.success("Atendimento excluído.")
                        st.cache_data.clear()
                    else:
                        st.warning("O atendimento selecionado não foi encontrado.")


def _renderizar_crud_referencias(consultar, engine):
    st.markdown("#### Referência simulada de população negra por distrito")
    st.caption(
        "Percentuais ilustrativos usados no mapa de diferença; não são "
        "estimativas oficiais do Censo por distrito."
    )
    registros = consultar("""
        SELECT distrito_sanitario_codigo,
               populacao_negra_pct_esperado
        FROM mock_populacao_negra_distrito
        ORDER BY distrito_sanitario_codigo
    """)
    st.dataframe(registros, width="stretch", hide_index=True)
    existentes = registros["distrito_sanitario_codigo"].astype(str).tolist()

    inserir_tab, alterar_tab, excluir_tab = st.tabs(
        ["Inserir", "Alterar", "Excluir"]
    )
    with inserir_tab:
        disponiveis = [codigo for codigo in DISTRITOS if codigo not in existentes]
        if not disponiveis:
            st.info("Todos os distritos já possuem uma referência.")
        else:
            with st.form("form_inserir_referencia"):
                distrito = st.selectbox(
                    "Distrito", disponiveis, key="novo_distrito_referencia",
                )
                percentual = st.number_input(
                    "Percentual esperado (0 a 1)", min_value=0.0, max_value=1.0,
                    value=0.0, step=0.001, format="%.3f",
                    help="Exemplo: 0,608 corresponde a 60,8%.",
                )
                enviado = st.form_submit_button("Inserir referência")
            if enviado:
                try:
                    inserir_referencia_distrito(engine, distrito, percentual)
                except SQLAlchemyError as erro:
                    st.error(f"Não foi possível inserir a referência: {erro}")
                else:
                    st.success("Referência distrital inserida.")
                    st.cache_data.clear()

    if not existentes:
        st.info("Não há referências para alterar ou excluir.")
        return

    with alterar_tab:
        distrito = st.selectbox(
            "Distrito para alterar", existentes,
            key="editar_distrito_referencia",
        )
        valor_atual = registros.loc[
            registros["distrito_sanitario_codigo"].astype(str) == distrito,
            "populacao_negra_pct_esperado",
        ].iloc[0]
        percentual_atual = (
            0.0 if pd.isna(valor_atual) else float(valor_atual)
        )
        with st.form("form_alterar_referencia"):
            percentual = st.number_input(
                "Novo percentual esperado (0 a 1)",
                min_value=0.0, max_value=1.0, value=percentual_atual,
                step=0.001, format="%.3f",
                help="Exemplo: 0,608 corresponde a 60,8%.",
                key=f"percentual_referencia_{distrito}",
            )
            enviado = st.form_submit_button("Salvar referência")
        if enviado:
            try:
                linhas = atualizar_referencia_distrito(
                    engine, distrito, percentual,
                )
            except SQLAlchemyError as erro:
                st.error(f"Não foi possível alterar a referência: {erro}")
            else:
                if linhas:
                    st.success("Referência distrital atualizada.")
                    st.cache_data.clear()
                else:
                    st.warning("A referência selecionada não foi encontrada.")

    with excluir_tab:
        with st.form("form_excluir_referencia"):
            distrito = st.selectbox(
                "Distrito para excluir", existentes,
                key="excluir_distrito_referencia",
            )
            confirmar = st.checkbox(
                "Confirmo a exclusão desta referência simulada.",
                key="confirmar_exclusao_referencia",
            )
            enviado = st.form_submit_button("Excluir referência")
        if enviado:
            if not confirmar:
                st.warning("Confirme a exclusão antes de continuar.")
            else:
                try:
                    linhas = excluir_referencia_distrito(engine, distrito)
                except SQLAlchemyError as erro:
                    st.error(f"Não foi possível excluir a referência: {erro}")
                else:
                    if linhas:
                        st.success("Referência distrital excluída.")
                        st.cache_data.clear()
                    else:
                        st.warning("A referência selecionada não foi encontrada.")


def _renderizar_consultas(consultar):
    st.caption(
        "Quatro consultas SQL predefinidas, incluindo junções entre tabelas. "
        "Os resultados podem ser visualizados em tabela e gráfico."
    )
    consulta_selecionada = st.selectbox(
        "Consulta", list(CONSULTAS), key="consulta_sql_equidados",
    )
    definicao = CONSULTAS[consulta_selecionada]
    st.code(definicao["sql"].strip(), language="sql")
    resultado = consultar(definicao["sql"])
    if resultado.empty:
        st.info("A consulta não retornou resultados.")
        return

    for coluna in definicao["colunas_numericas"]:
        resultado[coluna] = pd.to_numeric(resultado[coluna], errors="coerce")
    st.dataframe(resultado, width="stretch", hide_index=True)
    categoricas = resultado.select_dtypes(exclude="number").columns.tolist()
    numericas = resultado.select_dtypes(include="number").columns.tolist()
    if not categoricas or not numericas:
        st.info("O resultado não contém colunas suficientes para gerar um gráfico.")
        return

    coluna_x = st.selectbox(
        "Categoria do gráfico", categoricas,
        key=f"grafico_consulta_x_{consulta_selecionada}",
    )
    coluna_y = st.selectbox(
        "Indicador do gráfico", numericas,
        key=f"grafico_consulta_y_{consulta_selecionada}",
    )
    if definicao["tipo_grafico"] == "line":
        figura = px.line(
            resultado, x=coluna_x, y=coluna_y, markers=True,
            labels={coluna_x: coluna_x, coluna_y: coluna_y},
        )
    else:
        figura = px.bar(
            resultado, x=coluna_x, y=coluna_y, color=(
                "raca_cor" if "raca_cor" in resultado.columns else None
            ),
            labels={coluna_x: coluna_x, coluna_y: coluna_y},
        )
    figura.update_layout(
        template="plotly_white",
        margin={"l": 10, "r": 10, "t": 30, "b": 10},
    )
    st.plotly_chart(figura, width="stretch")


def pagina_dados(consultar, obter_engine):
    st.title("Dados e consultas SQL")
    st.caption(
        "Fontes: CNES e Censo IBGE nas páginas territoriais; nesta área, "
        "operações ficam limitadas aos dados fictícios/simulados."
    )
    st.warning(
        "Não use estes formulários para dados reais de pacientes. As tabelas "
        "mock_ são exclusivamente demonstrativas."
    )

    consultas_tab, cadastros_tab = st.tabs(
        ["Consultas e gráficos", "Inserir, alterar e excluir"]
    )
    with consultas_tab:
        _renderizar_consultas(consultar)
    with cadastros_tab:
        atendimentos_tab, referencias_tab = st.tabs(
            ["Atendimentos simulados", "Referências por distrito"]
        )
        engine = obter_engine()
        with atendimentos_tab:
            _renderizar_crud_atendimentos(consultar, engine)
        with referencias_tab:
            _renderizar_crud_referencias(consultar, engine)
