"""
Interface EquiDados para equidade em saúde, qualidade do cadastro e território.

Executar na raiz do repositório:
    streamlit run src/dashboard/app_dashboard.py
"""

import html
import json
import os
import sqlite3
import sys
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from folium.plugins import MarkerCluster
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")
GEOJSON_DIR = ROOT / "data" / "bronze" / "dados_recife"
PERCENTUAL_REFERENCIA_LGBTQIA = 0.04

# Premissas operacionais de planejamento para Atenção Básica.
# Essas taxas são cenários de gestão para dimensionamento territorial e não
# substituem os percentuais oficiais do Censo IBGE 2022.
PERCENTUAL_POPULACAO_ATENCAO_BASICA = 0.80
PERCENTUAL_DEFICIENCIA_ATENCAO_BASICA = 0.111
PERCENTUAL_RACA_COR_PLANEJAMENTO = {
    "Pardos": 0.485,
    "Pretos": 0.123,
    "Brancos": 0.388,
}
PERCENTUAL_LGBTQIA_SOBRE_POPULACAO_ATENCAO_BASICA = (
    PERCENTUAL_REFERENCIA_LGBTQIA * PERCENTUAL_POPULACAO_ATENCAO_BASICA
)
FATOR_DISTRIBUICAO_LITORAL = 0.8
FATOR_DISTRIBUICAO_INTERIOR = 1.2
CENTRO_RECIFE_LONGITUDE_LATITUDE = (-34.877, -8.063)

CORES_RACA_COR = {
    "Branca": "#7550c8",
    "Preta": "#d95f85",
    "Parda": "#ef9f62",
    "Amarela": "#e6c74f",
    "Indígena": "#42a99a",
}
CORES_INCONSISTENCIA = {
    "Campo em branco": "#d4c9e5",
    "Recusou informar": "#f0a45d",
    "Informou": "#46a77b",
}
ORDEM_INCONSISTENCIA = ["Campo em branco", "Recusou informar", "Informou"]
PALETA = ["#4b1594", "#8051c5", "#b18cde", "#e0d2f0"]

ROTULOS_DEFICIENCIA = {
    "Dificuldade permanente para enxergar, mesmo usando óculos ou lentes de contato": "Visual",
    "Dificuldade permanente para ouvir, mesmo usando aparelhos auditivos": "Auditiva",
    "Dificuldade permanente para andar ou subir degraus, mesmo usando prótese ou outro aparelho de auxílio": "Motora",
    "Dificuldade permanente para pegar pequenos objetos, como botão ou lápis, ou abrir e fechar tampas de garrafas, mesmo usando aparelho de auxílio": "Manual",
    "Dificuldade permanente para se comunicar, realizar cuidados pessoais, trabalhar ou estudar por causa de alguma limitação nas funções mentais": "Mental/Cognitiva",
}
DISTRITOS = {
    "01": "Distrito I",
    "02": "Distrito II",
    "03": "Distrito III",
    "04": "Distrito IV",
    "05": "Distrito V",
    "06": "Distrito VI",
    "07": "Distrito VII",
    "08": "Distrito VIII",
}

PAGINAS = {
    "Painel de Equidade": "◉",
    "Monitor de Cadastro": "▤",
    "Contexto Territorial": "⌖",
    "Insights de ML": "✦",
    "Dados e consultas SQL": "▦",
    "Assistente EquiDados": "✦",
}

st.set_page_config(
    page_title="EquiDados — Equidade em Saúde",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --purple: #42118f;
        --purple-dark: #31056f;
        --purple-mid: #6d3caf;
        --purple-pale: #f0eafa;
        --ink: #262033;
        --muted: #797486;
        --surface: #ffffff;
        --canvas: #f6f4f9;
        --line: #e9e5ef;
    }
    html, body, [data-testid="stAppViewContainer"] {
        background: var(--canvas);
        color: var(--ink);
        font-family: Inter, "Segoe UI", sans-serif;
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--purple-dark), #4c1597);
        min-width: 220px;
    }
    [data-testid="stSidebar"] * { color: #fff; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        border-radius: 9px;
        padding: 7px 9px;
        margin: 3px 0;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: rgba(255,255,255,.12);
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label p {
        font-size: 14px;
    }
    .brand-mark {
        width: 38px; height: 38px; border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        color: var(--purple); background: white; font-weight: 800;
        font-size: 18px; margin: 8px 0 9px;
    }
    .brand-name { font-size: 17px; font-weight: 750; margin-bottom: 2px; }
    .brand-subtitle { color: #d9c8f3; font-size: 11px; margin-bottom: 24px; }
    .sidebar-note {
        position: fixed; bottom: 22px; color: #d9c8f3;
        font-size: 11px; line-height: 1.5;
    }
    .page-heading {
        display: flex; align-items: center; justify-content: space-between;
        gap: 12px; margin: 4px 0 16px;
    }
    .page-heading h1 {
        font-size: 26px; color: var(--purple-dark); margin: 0;
        letter-spacing: -.5px;
    }
    .status-pill {
        background: #eee7f8; color: var(--purple); border-radius: 20px;
        padding: 7px 12px; font-size: 11px; font-weight: 650;
        white-space: nowrap;
    }
    .filter-title {
        color: var(--muted); font-size: 11px; font-weight: 700;
        text-transform: uppercase; letter-spacing: .06em;
        margin: 0 0 3px;
    }
    [data-testid="stMetric"] {
        background: var(--surface); border: 1px solid var(--line);
        border-radius: 12px; padding: 15px 17px;
        box-shadow: 0 2px 8px rgba(56, 28, 97, .035);
    }
    [data-testid="stMetricLabel"] p {
        color: var(--muted); font-size: 12px; font-weight: 550;
    }
    [data-testid="stMetricValue"] {
        color: var(--purple-dark); font-size: 25px; font-weight: 750;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--surface); border-color: var(--line) !important;
        border-radius: 12px;
    }
    h2, h3 { color: var(--purple-dark) !important; }
    h2 { font-size: 20px !important; }
    h3 { font-size: 16px !important; }
    [data-testid="stSelectbox"] label {
        color: #5c5669; font-size: 11px; font-weight: 650;
        min-height: 2.8em; display: flex; align-items: flex-end;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid var(--line); border-radius: 9px; overflow: hidden;
    }
    .progress-label {
        display: flex; justify-content: space-between; gap: 8px;
        color: #565064; font-size: 12px; margin: 9px 0 4px;
    }
    .progress-track {
        width: 100%; height: 9px; background: #e9e5ee;
        border-radius: 9px; overflow: hidden;
    }
    .progress-fill {
        height: 100%; background: linear-gradient(90deg, #4b1594, #8452c7);
        border-radius: 9px;
    }
    .notice {
        background: #f0eafa; border: 1px solid #e3d6f4;
        color: #563a78; border-radius: 9px; padding: 10px 13px;
        font-size: 12px; margin: 4px 0 14px;
    }
    .chat-hint {
        background: #f0eafa; border-radius: 10px; padding: 12px 14px;
        color: #57446e; font-size: 12px;
    }
    .small-muted { color: var(--muted); font-size: 11px; }
    .district-data-table {
        border-collapse: collapse;
        font-size: 11px;
        min-width: 520px;
    }
    .district-data-table th, .district-data-table td {
        border: 1px solid #ded8e8;
        padding: 4px 6px;
        text-align: left;
        vertical-align: top;
    }
    .district-data-table th { background: #f0eafa; }
    footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def obter_engine():
    if not NEON_DATABASE_URL:
        raise RuntimeError(
            "Configure NEON_DATABASE_URL no arquivo .env para conectar ao banco."
        )
    return create_engine(NEON_DATABASE_URL, pool_pre_ping=True)


@st.cache_resource
def carregar_geojson():
    arquivos = sorted(GEOJSON_DIR.glob("distritos_sanitarios_*.json"))
    if not arquivos:
        raise FileNotFoundError(
            f"Nenhum GeoJSON de distritos encontrado em {GEOJSON_DIR}"
        )
    with arquivos[-1].open(encoding="utf-8") as arquivo:
        geojson = json.load(arquivo)
    for feature in geojson["features"]:
        feature["properties"]["cdistscodi"] = str(
            feature["properties"]["cdistscodi"]
        )
    return geojson


@st.cache_data
def carregar_contexto_macroregiao_recife():
    caminho = (
        ROOT
        / "data"
        / "bronze"
        / "dados_recife"
        / "macroregiao_de_saude_recife.csv"
    )
    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo da macrorregião de saúde não encontrado: {caminho}"
        )
    dados = pd.read_csv(
        caminho,
        sep=";",
        dtype={"cod_municipio": str},
        encoding="utf-8-sig",
    )
    dados_recife = dados[dados["cod_municipio"] == "261160"]
    if len(dados_recife) != 1:
        raise ValueError(
            "O arquivo da macrorregião deve conter exatamente um registro "
            "para Recife (código IBGE 261160)."
        )
    return dados_recife.iloc[0].to_dict()


@st.cache_data(ttl=300)
def carregar_resumo_estabelecimentos_cnes_recife():
    arquivos = sorted(
        (ROOT / "data" / "bronze" / "cnes").glob(
            "estabelecimentos_recife_*.json"
        )
    )
    if not arquivos:
        raise FileNotFoundError(
            "Nenhum arquivo de estabelecimentos CNES de Recife foi encontrado."
        )
    with arquivos[-1].open(encoding="utf-8") as arquivo:
        estabelecimentos = json.load(arquivo)
    if not isinstance(estabelecimentos, list) or not estabelecimentos:
        raise ValueError(
            f"O arquivo CNES não contém uma lista válida: {arquivos[-1]}"
        )
    if any("atendeSus" not in estabelecimento for estabelecimento in estabelecimentos):
        raise ValueError(
            f"O arquivo CNES não contém o campo 'atendeSus': {arquivos[-1]}"
        )
    return {
        "total": len(estabelecimentos),
        "atendem_sus": sum(
            estabelecimento["atendeSus"] == "S"
            for estabelecimento in estabelecimentos
        ),
    }


@st.cache_data(ttl=300)
def carregar_unidades_geograficas():
    unidades = consultar(
        """
        SELECT cnes, nome_fantasia, nome_empresarial, tipo_estabelecimento,
               endereco, cep, bairro,
               distrito_sanitario_codigo, latitude, longitude
        FROM unidades_saude
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
    )
    unidades["latitude"] = pd.to_numeric(unidades["latitude"], errors="coerce")
    unidades["longitude"] = pd.to_numeric(unidades["longitude"], errors="coerce")
    unidades = unidades.dropna(subset=["latitude", "longitude"])
    unidades = unidades[
        unidades["latitude"].between(-90, 90)
        & unidades["longitude"].between(-180, 180)
    ].copy()
    pontos = gpd.GeoDataFrame(
        unidades,
        geometry=gpd.points_from_xy(unidades["longitude"], unidades["latitude"]),
        crs="EPSG:4326",
    )
    limites = gpd.GeoDataFrame.from_features(
        carregar_geojson()["features"],
        crs="EPSG:4326",
    )[["cdistscodi", "geometry"]]
    limites["cdistscodi"] = limites["cdistscodi"].map(
        lambda valor: f"{int(valor):02d}"
    )
    pontos = gpd.sjoin(
        pontos,
        limites,
        how="left",
        predicate="within",
    ).drop(columns=["index_right"], errors="ignore")
    pontos["coordenada_dentro_distrito"] = pontos["cdistscodi"].notna()
    pontos["distrito_mapa"] = pontos["cdistscodi"].fillna(
        pontos["distrito_sanitario_codigo"]
    )
    pontos["distrito_mapa"] = pontos["distrito_mapa"].map(
        lambda valor: (
            f"{int(valor):02d}" if pd.notna(valor) and str(valor).isdigit()
            else None
        )
    )
    return pontos


def distribuir_estimativas_com_gradiente_interior(percentuais, geojson):
    distritos = gpd.GeoDataFrame.from_features(
        geojson["features"],
        crs="EPSG:4326",
    )
    distritos["codigo"] = distritos["cdistscodi"].map(
        lambda codigo: f"{int(codigo):02d}"
    )
    distritos_metricos = distritos.to_crs("EPSG:31985")
    pontos_representativos = {
        codigo: geometria.representative_point().x
        for codigo, geometria in zip(distritos["codigo"], distritos_metricos.geometry)
    }
    pontos_distrito = {
        codigo: geometria.representative_point()
        for codigo, geometria in zip(distritos["codigo"], distritos_metricos.geometry)
    }
    centro_recife = gpd.GeoSeries(
        gpd.points_from_xy(
            [CENTRO_RECIFE_LONGITUDE_LATITUDE[0]],
            [CENTRO_RECIFE_LONGITUDE_LATITUDE[1]],
        ),
        crs="EPSG:4326",
    ).to_crs("EPSG:31985").iloc[0]

    resultado = percentuais.copy()
    resultado["coordenada_x"] = resultado[
        "distrito_sanitario_codigo"
    ].map(pontos_representativos)
    resultado["distancia_centro"] = resultado[
        "distrito_sanitario_codigo"
    ].map(lambda codigo: pontos_distrito[codigo].distance(centro_recife))
    if resultado["coordenada_x"].isna().any():
        raise ValueError(
            "Há distritos sem geometria para calcular a distribuição territorial."
        )

    def normalizar_entre_zero_e_um(valores):
        menor = valores.min()
        maior = valores.max()
        if maior == menor:
            return pd.Series(0.5, index=resultado.index)
        return (valores - menor) / (maior - menor)

    distancia_litoral_aproximada = normalizar_entre_zero_e_um(
        resultado["coordenada_x"].max() - resultado["coordenada_x"]
    )
    distancia_centro = normalizar_entre_zero_e_um(
        resultado["distancia_centro"]
    )
    indice_interior = (
        distancia_litoral_aproximada + distancia_centro
    ) / 2
    fator_territorial = FATOR_DISTRIBUICAO_LITORAL + (
        FATOR_DISTRIBUICAO_INTERIOR - FATOR_DISTRIBUICAO_LITORAL
    ) * indice_interior

    def distribuir_total(coluna, coluna_populacao):
        total = int(resultado[coluna].sum())
        pesos = resultado[coluna_populacao] * fator_territorial
        soma_pesos = pesos.sum()
        quotas = {
            codigo: total * peso / soma_pesos
            for codigo, peso in zip(
                resultado["distrito_sanitario_codigo"],
                pesos,
            )
        }
        alocacoes = {
            codigo: int(quota)
            for codigo, quota in quotas.items()
        }
        faltantes = total - sum(alocacoes.values())
        ordem = sorted(
            quotas,
            key=lambda codigo: (
                -(quotas[codigo] - alocacoes[codigo]),
                codigo,
            ),
        )
        for codigo in ordem[:faltantes]:
            alocacoes[codigo] += 1
        return resultado["distrito_sanitario_codigo"].map(alocacoes)

    for coluna in ("populacao_parda_estimada", "populacao_preta_estimada"):
        resultado[coluna] = distribuir_total(
            coluna,
            "populacao_total_estimada",
        )
    resultado["populacao_com_deficiencia_estimada"] = distribuir_total(
        "populacao_com_deficiencia_estimada",
        "populacao_total_estimada",
    )
    resultado["populacao_lgbtqia_atencao_basica_estimada"] = distribuir_total(
        "populacao_lgbtqia_atencao_basica_estimada",
        "populacao_atencao_basica_estimada",
    )
    resultado["populacao_negra_estimada"] = (
        resultado["populacao_parda_estimada"]
        + resultado["populacao_preta_estimada"]
    )
    for coluna, total in (
        ("populacao_negra_estimada", "populacao_negra_total_estimada"),
        ("populacao_parda_estimada", "populacao_parda_total_estimada"),
        ("populacao_preta_estimada", "populacao_preta_total_estimada"),
        (
            "populacao_com_deficiencia_estimada",
            "populacao_pcd_total_estimada",
        ),
    ):
        resultado[total] = int(resultado[coluna].sum())
    resultado["percentual_negra_no_distrito"] = (
        resultado["populacao_negra_estimada"]
        / resultado["populacao_total_estimada"]
    )
    resultado["percentual_parda_no_distrito"] = (
        resultado["populacao_parda_estimada"]
        / resultado["populacao_total_estimada"]
    )
    resultado["percentual_preta_no_distrito"] = (
        resultado["populacao_preta_estimada"]
        / resultado["populacao_total_estimada"]
    )
    resultado["percentual_pcd_no_distrito"] = (
        resultado["populacao_com_deficiencia_estimada"]
        / resultado["populacao_total_estimada"]
    )
    resultado["percentual_lgbtqia_na_atencao_basica"] = (
        resultado["populacao_lgbtqia_atencao_basica_estimada"]
        / resultado["populacao_atencao_basica_estimada"]
    )
    return resultado.drop(
        columns=["coordenada_x", "distancia_centro"]
    )


@st.cache_data
def carregar_farmacias_populares():
    caminho = ROOT / "data" / "bronze" / "farmacias_populares_recife.json"
    if not caminho.exists():
        raise FileNotFoundError(
            f"Arquivo das farmácias populares não encontrado: {caminho}"
        )
    with caminho.open(encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    farmacias = pd.DataFrame(dados["records"])
    if farmacias.empty:
        raise ValueError("O arquivo das farmácias populares não contém registros.")
    farmacias["distrito_sanitario_codigo"] = farmacias[
        "distrito_sanitario_codigo"
    ].map(lambda codigo: f"{int(codigo):02d}")
    return farmacias


@st.cache_data
def carregar_percentuais_populacao_distrito():
    caminho = ROOT / "data" / "bronze" / "mock_pec" / "pec_formulario_recife.sqlite"
    if not caminho.exists():
        raise FileNotFoundError(
            f"Base de estimativas distritais não encontrada: {caminho}"
        )
    consulta_sql = """
        SELECT distrito_sanitario_codigo,
               populacao_total_estimada,
               populacao_atencao_basica_estimada,
               populacao_negra_estimada,
               populacao_parda_estimada,
               populacao_preta_estimada,
               populacao_com_deficiencia_estimada,
               populacao_lgbtqia_atencao_basica_estimada,
               SUM(populacao_negra_estimada) OVER ()
                   AS populacao_negra_total_estimada,
               SUM(populacao_parda_estimada) OVER ()
                   AS populacao_parda_total_estimada,
               SUM(populacao_preta_estimada) OVER ()
                   AS populacao_preta_total_estimada,
               SUM(populacao_com_deficiencia_estimada) OVER ()
                   AS populacao_pcd_total_estimada,
               SUM(populacao_lgbtqia_atencao_basica_estimada) OVER ()
                   AS populacao_lgbtqia_total_estimada
        FROM distrito_populacao
        ORDER BY distrito_sanitario_codigo
    """
    with sqlite3.connect(caminho) as conexao:
        percentuais = pd.read_sql_query(consulta_sql, conexao)
    if percentuais.empty:
        raise ValueError(
            "A base de estimativas distritais não contém percentuais."
        )
    percentuais["distrito_sanitario_codigo"] = percentuais[
        "distrito_sanitario_codigo"
    ].astype(str).str.zfill(2)
    return distribuir_estimativas_com_gradiente_interior(
        percentuais,
        carregar_geojson(),
    )


@st.cache_data(ttl=300)
def carregar_unidades_cadastradas():
    return consultar(
        """
        SELECT cnes, nome_fantasia, nome_empresarial, tipo_estabelecimento,
               endereco, cep, bairro, distrito_sanitario_codigo,
               latitude, longitude
        FROM unidades_saude
        """
    )


def consultar(sql, params=None):
    return pd.read_sql(text(sql), obter_engine(), params=params or {})


@st.cache_data
def carregar_indicadores_censo():
    arquivos_raca = sorted(
        (ROOT / "data" / "bronze" / "ibge").glob("censo_raca_cor_recife_*.json")
    )
    arquivos_deficiencia = sorted(
        (ROOT / "data" / "bronze" / "ibge").glob(
            "censo_deficiencia_tipo_recife_*.json"
        )
    )
    if not arquivos_raca or not arquivos_deficiencia:
        raise FileNotFoundError(
            "Os arquivos brutos do Censo de raça/cor e deficiência são "
            "necessários para calcular os denominadores populacionais."
        )

    with arquivos_raca[-1].open(encoding="utf-8") as arquivo:
        dados_raca = json.load(arquivo)
    with arquivos_deficiencia[-1].open(encoding="utf-8") as arquivo:
        dados_deficiencia = json.load(arquivo)

    total_populacao = next(
        int(registro["V"])
        for registro in dados_raca[1:]
        if registro.get("D2C") == "93"
        and registro.get("D4N") == "Total"
    )
    populacao_preta = next(
        int(registro["V"])
        for registro in dados_raca[1:]
        if registro.get("D2C") == "93"
        and registro.get("D4N") == "Preta"
    )
    populacao_parda = next(
        int(registro["V"])
        for registro in dados_raca[1:]
        if registro.get("D2C") == "93"
        and registro.get("D4N") == "Parda"
    )
    populacao_com_deficiencia = next(
        int(registro["V"])
        for registro in dados_deficiencia[1:]
        if registro.get("D2C") == "12785"
        and registro.get("D4N") == "Total"
    )
    populacao_com_2_anos_ou_mais = next(
        int(registro["V"])
        for registro in dados_deficiencia[1:]
        if registro.get("D2C") == "11852"
        and registro.get("D4N") == "Total"
    )
    return {
        "ano": int(dados_raca[1]["D3N"]),
        "populacao_total": total_populacao,
        "populacao_negra": populacao_preta + populacao_parda,
        "percentual_negra": (
            (populacao_preta + populacao_parda) / total_populacao * 100
        ),
        "populacao_com_deficiencia": populacao_com_deficiencia,
        "populacao_referencia_deficiencia": populacao_com_2_anos_ou_mais,
        "percentual_com_deficiencia": (
            populacao_com_deficiencia / populacao_com_2_anos_ou_mais * 100
        ),
    }


def estimar_populacao_lgbtqia(populacao, percentual):
    return round(populacao * percentual)


def preparar_grafico(fig, altura=300):
    fig.update_layout(
        template="plotly_white",
        height=altura,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Inter, Segoe UI, sans-serif", color="#514b5e", size=11),
        colorway=PALETA,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0,
            font=dict(color="#514b5e"),
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor="#e8e4ed",
        tickfont=dict(color="#514b5e"),
        title_font=dict(color="#514b5e"),
    )
    fig.update_yaxes(
        gridcolor="#efedf2",
        zeroline=False,
        tickfont=dict(color="#514b5e"),
        title_font=dict(color="#514b5e"),
    )
    return fig


def rotulo_distrito(codigo):
    return DISTRITOS.get(str(codigo), f"Distrito {codigo}")


def mapa_distrito(df, coluna_valor, titulo, escala="Purples", rotulo_valor=None):
    df = df.copy()
    if not df.empty:
        df["cdistscodi"] = df["cdistscodi"].astype(str)
    rotulo = rotulo_valor or coluna_valor
    geojson = carregar_geojson()
    geojson_com_valor = json.loads(json.dumps(geojson))
    valores = (
        dict(zip(df["cdistscodi"], df[coluna_valor]))
        if not df.empty
        else {}
    )
    for feature in geojson_com_valor["features"]:
        codigo = feature["properties"]["cdistscodi"]
        feature["properties"]["valor_tooltip"] = valores.get(codigo, 0)

    mapa = folium.Map(
        location=[-8.05, -34.90],
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    if not df.empty:
        folium.Choropleth(
            geo_data=geojson_com_valor,
            data=df,
            columns=["cdistscodi", coluna_valor],
            key_on="feature.properties.cdistscodi",
            fill_color=escala,
            fill_opacity=0.78,
            line_opacity=0.5,
            line_color="#ffffff",
            legend_name=rotulo,
            nan_fill_color="#eeeaf2",
        ).add_to(mapa)
    folium.GeoJson(
        geojson_com_valor,
        style_function=lambda _: {"fillOpacity": 0, "weight": 0.5, "color": "#fff"},
        tooltip=folium.GeoJsonTooltip(
            fields=["cdistscodi", "valor_tooltip"],
            aliases=["Distrito", rotulo],
        ),
    ).add_to(mapa)
    st.markdown(f"**{titulo}**")
    return mapa


def mapa_unidades_saude(
    unidades,
    geojson,
    distrito_selecionado,
    farmacias,
    unidades_cadastradas,
    percentuais_distritos,
):
    geojson_mapa = json.loads(json.dumps(geojson))
    unidades_detalhe = unidades_cadastradas.copy()

    def normalizar_codigo_distrito(valor):
        if pd.isna(valor) or not str(valor).strip():
            return None
        codigo = str(valor).strip()
        if codigo.endswith(".0"):
            codigo = codigo[:-2]
        return codigo.zfill(2) if codigo.isdigit() else None

    unidades_detalhe["distrito_mapa"] = unidades_detalhe[
        "distrito_sanitario_codigo"
    ].map(normalizar_codigo_distrito)
    distrito_por_cnes = (
        unidades.dropna(subset=["distrito_mapa"])
        .drop_duplicates("cnes")
        .set_index("cnes")["distrito_mapa"]
    )
    distrito_geografico = unidades_detalhe["cnes"].map(distrito_por_cnes)
    unidades_detalhe["distrito_mapa"] = unidades_detalhe[
        "distrito_mapa"
    ].fillna(distrito_geografico)
    contagens = (
        unidades_detalhe["distrito_mapa"].value_counts(dropna=True).to_dict()
    )
    contagens_mapeadas = unidades["distrito_mapa"].value_counts(
        dropna=True
    ).to_dict()
    contagens_farmacias = (
        farmacias["distrito_sanitario_codigo"].value_counts().to_dict()
    )
    percentuais_por_distrito = percentuais_distritos.set_index(
        "distrito_sanitario_codigo"
    ).to_dict(orient="index")
    def valor_html(valor):
        if pd.isna(valor) or not str(valor).strip():
            return "Não informado"
        return html.escape(str(valor))

    for feature in geojson_mapa["features"]:
        codigo = f"{int(feature['properties']['cdistscodi']):02d}"
        feature["properties"]["cdistscodi"] = codigo
        unidades_distrito = (
            unidades_detalhe[unidades_detalhe["distrito_mapa"] == codigo]
            .sort_values("nome_fantasia", na_position="last")
        )
        farmacias_distrito = farmacias[
            farmacias["distrito_sanitario_codigo"] == codigo
        ].sort_values("farmacia", na_position="last")
        total_unidades = int(contagens.get(codigo, 0))
        total_unidades_mapeadas = int(contagens_mapeadas.get(codigo, 0))
        total_farmacias = int(contagens_farmacias.get(codigo, 0))
        feature["properties"]["unidades_cadastradas"] = total_unidades
        feature["properties"]["farmacias_populares"] = total_farmacias
        percentuais = percentuais_por_distrito.get(codigo, {})
        populacao_residente = percentuais.get("populacao_total_estimada")
        populacao_atencao_basica = percentuais.get(
            "populacao_atencao_basica_estimada"
        )
        def formatar_contagem(valor):
            return (
                f"{int(round(float(valor))):,}".replace(",", ".")
                if pd.notna(valor)
                else "Sem estimativa"
            )

        def formatar_parcela(numerador, denominador):
            if pd.isna(numerador) or pd.isna(denominador) or float(denominador) <= 0:
                return "Sem estimativa"
            return f"{float(numerador) / float(denominador):.1%}".replace(
                ".", ","
            )

        feature["properties"]["populacao_residente_tooltip"] = (
            formatar_contagem(populacao_residente)
        )
        populacao_negra_distrito = percentuais.get(
            "populacao_negra_estimada"
        )
        populacao_parda_distrito = percentuais.get(
            "populacao_parda_estimada"
        )
        populacao_preta_distrito = percentuais.get(
            "populacao_preta_estimada"
        )
        populacao_pcd_distrito = percentuais.get(
            "populacao_com_deficiencia_estimada"
        )
        populacao_lgbtqia_distrito = percentuais.get(
            "populacao_lgbtqia_atencao_basica_estimada"
        )
        feature["properties"]["populacao_negra_tooltip"] = formatar_parcela(
            populacao_negra_distrito,
            populacao_residente,
        )
        feature["properties"]["populacao_negra_qtd_tooltip"] = formatar_contagem(
            populacao_negra_distrito
        )
        feature["properties"]["parda_tooltip"] = formatar_parcela(
            populacao_parda_distrito,
            populacao_residente,
        )
        feature["properties"]["parda_qtd_tooltip"] = formatar_contagem(
            populacao_parda_distrito
        )
        feature["properties"]["preta_tooltip"] = formatar_parcela(
            populacao_preta_distrito,
            populacao_residente,
        )
        feature["properties"]["preta_qtd_tooltip"] = formatar_contagem(
            populacao_preta_distrito
        )
        feature["properties"]["pcd_tooltip"] = formatar_parcela(
            populacao_pcd_distrito,
            populacao_residente,
        )
        feature["properties"]["pcd_qtd_tooltip"] = formatar_contagem(
            populacao_pcd_distrito
        )
        feature["properties"]["lgbtqia_tooltip"] = formatar_parcela(
            populacao_lgbtqia_distrito,
            populacao_atencao_basica,
        )
        feature["properties"]["lgbtqia_qtd_tooltip"] = formatar_contagem(
            populacao_lgbtqia_distrito
        )

        linhas_unidades = []
        for unidade in unidades_distrito.itertuples(index=False):
            nome = valor_html(unidade.nome_fantasia)
            coordenadas = (
                f"{float(unidade.latitude):.5f}, {float(unidade.longitude):.5f}"
                if pd.notna(unidade.latitude) and pd.notna(unidade.longitude)
                else "Sem coordenadas"
            )
            linhas_unidades.append(
                "<tr>"
                f"<td>{valor_html(unidade.cnes)}</td>"
                f"<td>{nome}</td>"
                f"<td>{valor_html(unidade.nome_empresarial)}</td>"
                f"<td>{valor_html(unidade.tipo_estabelecimento)}</td>"
                f"<td>{valor_html(unidade.endereco)}</td>"
                f"<td>{valor_html(unidade.bairro)}</td>"
                f"<td>{valor_html(unidade.cep)}</td>"
                f"<td>{coordenadas}</td>"
                "</tr>"
            )
        tabela_unidades = (
            "<p>Nenhuma unidade cadastrada neste distrito.</p>"
            if not linhas_unidades
            else (
                '<div style="max-height:260px;overflow:auto">'
                '<table class="district-data-table"><thead><tr>'
                "<th>CNES</th><th>Nome fantasia</th><th>Nome empresarial</th>"
                "<th>Tipo</th><th>Endereço</th><th>Bairro</th><th>CEP</th>"
                "<th>Coordenadas</th></tr></thead><tbody>"
                + "".join(linhas_unidades)
                + "</tbody></table></div>"
            )
        )

        linhas_farmacias = [
            "<tr>"
            f"<td>{valor_html(farmacia.cnpj)}</td>"
            f"<td>{valor_html(farmacia.farmacia)}</td>"
            f"<td>{valor_html(farmacia.endereco)}</td>"
            f"<td>{valor_html(farmacia.bairro)}</td>"
            "</tr>"
            for farmacia in farmacias_distrito.itertuples(index=False)
        ]
        tabela_farmacias = (
            "<p>Nenhuma farmácia do anexo associada a este distrito.</p>"
            if not linhas_farmacias
            else (
                '<div style="max-height:220px;overflow:auto">'
                '<table class="district-data-table"><thead><tr>'
                "<th>CNPJ</th><th>Farmácia</th><th>Logradouro</th>"
                "<th>Bairro</th></tr></thead><tbody>"
                + "".join(linhas_farmacias)
                + "</tbody></table></div>"
            )
        )
        feature["properties"]["detalhes_html"] = (
            '<div style="min-width:520px;max-width:760px">'
            f"<h3>{html.escape(rotulo_distrito(codigo))}</h3>"
            f"<p><b>Unidades cadastradas:</b> {total_unidades} "
            f"({total_unidades_mapeadas} com coordenadas) &nbsp; "
            f"<b>Farmácias do anexo:</b> {total_farmacias}</p>"
            "<h4>Unidades de saúde</h4>"
            f"{tabela_unidades}"
            "<h4>Farmácias populares — planilha anexada</h4>"
            f"{tabela_farmacias}"
            '<p style="font-size:11px;color:#666">'
            "As farmácias foram associadas ao distrito pelo bairro informado; "
            "a planilha não contém coordenadas, portanto sua posição exata não "
            "é representada no mapa.</p></div>"
        )

    mapa = folium.Map(
        location=[-8.05, -34.90],
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    folium.GeoJson(
        geojson_mapa,
        name="Distritos Sanitários",
        style_function=lambda feature: {
            "fillColor": "#8051c5",
            "color": "#4b1594",
            "weight": 3 if (
                distrito_selecionado != "Todos"
                and feature["properties"]["cdistscodi"] == distrito_selecionado
            ) else 1.5,
            "fillOpacity": 0.38 if (
                distrito_selecionado != "Todos"
                and feature["properties"]["cdistscodi"] == distrito_selecionado
            ) else 0.12,
        },
        highlight_function=lambda _: {
            "weight": 3,
            "fillOpacity": 0.4,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "cdistscodi",
                "populacao_negra_tooltip",
                "populacao_negra_qtd_tooltip",
                "pcd_tooltip",
                "pcd_qtd_tooltip",
                "lgbtqia_tooltip",
                "lgbtqia_qtd_tooltip",
                "unidades_cadastradas",
                "farmacias_populares",
            ],
            aliases=[
                "Distrito Sanitário",
                "Pretas + pardas (%)",
                "Pessoas pretas + pardas (quantidade)",
                "PCD (%)",
                "Pessoas com deficiência (quantidade)",
                "LGBTQIA+ (%)",
                "Pessoas LGBTQIA+ (quantidade)",
                "Unidades cadastradas",
                "Farmácias populares",
            ],
            sticky=True,
        ),
        popup=folium.GeoJsonPopup(
            fields=["detalhes_html"],
            labels=False,
            localize=False,
            max_width=780,
            max_height=520,
        ),
    ).add_to(mapa)

    if unidades.empty:
        unidades_visiveis = unidades
    elif distrito_selecionado == "Todos":
        unidades_visiveis = unidades
    else:
        unidades_visiveis = unidades[
            unidades["distrito_mapa"] == distrito_selecionado
        ]

    marcadores = MarkerCluster(
        name="Unidades de Saúde",
        overlay=True,
        control=True,
        show=True,
    ).add_to(mapa)
    unidades_com_coordenada_no_distrito = unidades_visiveis[
        unidades_visiveis["coordenada_dentro_distrito"]
    ]
    unidades_com_coordenada_externa = unidades_visiveis[
        ~unidades_visiveis["coordenada_dentro_distrito"]
    ]
    for unidade in unidades_com_coordenada_no_distrito.itertuples(index=False):
        nome = html.escape(str(unidade.nome_fantasia or "Unidade sem nome"))
        tipo = html.escape(str(unidade.tipo_estabelecimento or "Não informado"))
        bairro = html.escape(str(unidade.bairro or "Não informado"))
        codigo = str(unidade.distrito_mapa or "Não informado")
        distrito = html.escape(rotulo_distrito(codigo))
        popup = folium.Popup(
            (
                f"<b>{nome}</b><br>"
                f"CNES: {html.escape(str(unidade.cnes))}<br>"
                f"Tipo: {tipo}<br>"
                f"Bairro: {bairro}<br>"
                f"{distrito}"
            ),
            max_width=300,
        )
        folium.Marker(
            location=[unidade.latitude, unidade.longitude],
            tooltip=nome,
            popup=popup,
            icon=folium.Icon(color="purple", icon="plus-sign"),
        ).add_to(marcadores)

    distritos_layer = gpd.GeoDataFrame.from_features(
        geojson_mapa["features"],
        crs="EPSG:4326",
    ).set_index("cdistscodi")
    unidades_externas_por_distrito = unidades_com_coordenada_externa.dropna(
        subset=["distrito_mapa"]
    )
    for codigo, grupo in unidades_externas_por_distrito.groupby("distrito_mapa"):
        if codigo not in distritos_layer.index:
            continue
        ponto_representativo = distritos_layer.loc[
            codigo, "geometry"
        ].representative_point()
        lista_unidades = "".join(
            f"<li>{valor_html(unidade.nome_fantasia)} — "
            f"CNES {valor_html(unidade.cnes)}</li>"
            for unidade in grupo.itertuples(index=False)
        )
        folium.CircleMarker(
            location=[ponto_representativo.y, ponto_representativo.x],
            radius=8,
            color="#8c3b00",
            fill=True,
            fill_color="#f28c28",
            fill_opacity=0.9,
            tooltip=(
                f"{len(grupo)} unidade(s) com coordenadas fora dos limites; "
                f"posição aproximada no {rotulo_distrito(codigo)}"
            ),
            popup=folium.Popup(
                "<b>Unidades com localização aproximada no distrito</b>"
                f"<ul>{lista_unidades}</ul>"
                "<small>As coordenadas cadastradas estão fora dos limites "
                "dos distritos; o marcador indica apenas o distrito "
                "informado no cadastro.</small>",
                max_width=420,
            ),
        ).add_to(mapa)

    marcadores_farmacias = folium.FeatureGroup(
        name="Farmácias do anexo — área aproximada por distrito",
        overlay=True,
        control=True,
        show=True,
    ).add_to(mapa)
    farmacias_visiveis = (
        farmacias
        if distrito_selecionado == "Todos"
        else farmacias[
            farmacias["distrito_sanitario_codigo"] == distrito_selecionado
        ]
    )
    for codigo, grupo in farmacias_visiveis.groupby("distrito_sanitario_codigo"):
        ponto_representativo = distritos_layer.loc[
            codigo, "geometry"
        ].representative_point()
        lista_farmacias = "".join(
            (
                "<li><b>"
                f"{valor_html(farmacia.farmacia)}"
                "</b> — "
                f"{valor_html(farmacia.endereco)}, "
                f"{valor_html(farmacia.bairro)} "
                f"(CNPJ {valor_html(farmacia.cnpj)})</li>"
            )
            for farmacia in grupo.itertuples(index=False)
        )
        popup_farmacias = (
            f"<b>{html.escape(rotulo_distrito(codigo))}: "
            f"{len(grupo)} farmácias</b>"
            "<ul>"
            f"{lista_farmacias}"
            "</ul>"
            "<small>Marcador indicativo do distrito, não da localização "
            "exata das lojas.</small>"
        )
        folium.CircleMarker(
            location=[ponto_representativo.y, ponto_representativo.x],
            radius=10,
            color="#a34d00",
            fill=True,
            fill_color="#f28c28",
            fill_opacity=0.9,
            tooltip=(
                f"{rotulo_distrito(codigo)} — {len(grupo)} farmácias "
                "(área aproximada)"
            ),
            popup=folium.Popup(popup_farmacias, max_width=420, max_height=400),
        ).add_to(marcadores_farmacias)

    minx, miny, maxx, maxy = gpd.GeoDataFrame.from_features(
        geojson["features"],
        crs="EPSG:4326",
    ).total_bounds
    mapa.fit_bounds([[miny, minx], [maxy, maxx]])
    folium.LayerControl(collapsed=True).add_to(mapa)
    return mapa


def renderizar_progresso(rotulo, percentual):
    if pd.isna(percentual):
        percentual = 0
    valor = max(0.0, min(float(percentual), 100.0))
    st.markdown(
        f"""
        <div class="progress-label"><span>{rotulo}</span><b>{valor:.1f}%</b></div>
        <div class="progress-track"><div class="progress-fill"
        style="width:{valor:.1f}%"></div></div>
        """,
        unsafe_allow_html=True,
    )


def obter_opcoes_filtros():
    distritos = consultar(
        """
        SELECT DISTINCT distrito_sanitario_codigo AS valor
        FROM mock_pec_atendimentos
        WHERE distrito_sanitario_codigo IS NOT NULL
        ORDER BY valor
        """
    )["valor"].tolist()
    equipes = consultar(
        """
        SELECT DISTINCT codigo_equipe AS valor
        FROM mock_pec_atendimentos
        WHERE codigo_equipe IS NOT NULL
        ORDER BY valor
        """
    )["valor"].tolist()
    unidades_df = consultar(
        """
        SELECT DISTINCT a.cnes_unidade AS valor,
               COALESCE(u.nome_fantasia, a.cnes_unidade) AS rotulo
        FROM mock_pec_atendimentos a
        LEFT JOIN unidades_saude u ON u.cnes = a.cnes_unidade
        WHERE a.cnes_unidade IS NOT NULL
        ORDER BY rotulo
        """
    )
    racas = consultar(
        "SELECT DISTINCT raca_cor AS valor FROM mock_pec_atendimentos "
        "WHERE raca_cor IS NOT NULL ORDER BY valor"
    )["valor"].tolist()
    generos = consultar(
        "SELECT DISTINCT identidade_genero AS valor FROM mock_pec_atendimentos "
        "WHERE identidade_genero IS NOT NULL ORDER BY valor"
    )["valor"].tolist()
    orientacoes = consultar(
        "SELECT DISTINCT orientacao_sexual AS valor FROM mock_pec_atendimentos "
        "WHERE orientacao_sexual IS NOT NULL ORDER BY valor"
    )["valor"].tolist()
    deficiencias = consultar(
        """
        SELECT DISTINCT deficiencia_tipo AS valor FROM mock_pec_atendimentos
        WHERE deficiencia_tipo IS NOT NULL AND deficiencia_tipo != 'Nenhuma'
        ORDER BY valor
        """
    )["valor"].tolist()
    return {
        "distritos": distritos,
        "equipes": equipes,
        "unidades": unidades_df,
        "racas": racas,
        "generos": generos,
        "orientacoes": orientacoes,
        "deficiencias": deficiencias,
    }


def renderizar_filtros():
    opcoes = obter_opcoes_filtros()
    unidades_rotulo = dict(
        zip(opcoes["unidades"]["valor"], opcoes["unidades"]["rotulo"])
    )
    with st.container(border=True):
        linha_territorio = st.columns(4, gap="medium")
        with linha_territorio[0]:
            distrito = st.selectbox(
                "Distrito Sanitário",
                ["Todos"] + opcoes["distritos"],
                format_func=lambda valor: (
                    "Todos" if valor == "Todos" else rotulo_distrito(valor)
                ),
                key="filtro_distrito",
            )
        with linha_territorio[1]:
            equipe = st.selectbox(
                "Equipe de Saúde",
                ["Todas"] + opcoes["equipes"],
                key="filtro_equipe",
            )
        with linha_territorio[2]:
            unidade = st.selectbox(
                "Unidade de Saúde",
                ["Todas"] + opcoes["unidades"]["valor"].tolist(),
                format_func=lambda valor: (
                    "Todas" if valor == "Todas" else unidades_rotulo.get(valor, valor)
                ),
                key="filtro_unidade",
            )
        with linha_territorio[3]:
            raca = st.selectbox(
                "Raça/Cor", ["Todas"] + opcoes["racas"], key="filtro_raca"
            )

        linha_perfil = st.columns(3, gap="medium")
        with linha_perfil[0]:
            genero = st.selectbox(
                "Identidade de Gênero",
                ["Todas"] + opcoes["generos"],
                key="filtro_genero",
            )
        with linha_perfil[1]:
            orientacao = st.selectbox(
                "Orientação Sexual",
                ["Todas"] + opcoes["orientacoes"],
                key="filtro_orientacao",
            )
        with linha_perfil[2]:
            deficiencia = st.selectbox(
                "Deficiência",
                ["Todos os tipos"] + opcoes["deficiencias"],
                format_func=lambda valor: (
                    valor
                    if valor == "Todos os tipos"
                    else ROTULOS_DEFICIENCIA.get(valor, valor)
                ),
                key="filtro_deficiencia",
            )

    st.session_state["filtros_equidados"] = {
        "distrito": distrito,
        "equipe": equipe,
        "unidade": unidade,
        "raca": raca,
        "genero": genero,
        "orientacao": orientacao,
        "deficiencia": deficiencia,
    }


def filtro_mock(alias="a", incluir_deficiencia=True):
    filtros = st.session_state.get("filtros_equidados", {})
    correspondencias = [
        ("distrito", "distrito_sanitario_codigo", "Todos"),
        ("equipe", "codigo_equipe", "Todas"),
        ("unidade", "cnes_unidade", "Todas"),
        ("raca", "raca_cor", "Todas"),
        ("genero", "identidade_genero", "Todas"),
        ("orientacao", "orientacao_sexual", "Todas"),
    ]
    clausulas = []
    parametros = {}
    for chave, coluna, padrao in correspondencias:
        valor = filtros.get(chave, padrao)
        if valor != padrao:
            parametro = f"filtro_{chave}"
            clausulas.append(f"{alias}.{coluna} = :{parametro}")
            parametros[parametro] = valor
    tipo = filtros.get("deficiencia", "Todos os tipos")
    if incluir_deficiencia and tipo != "Todos os tipos":
        clausulas.append(f"{alias}.deficiencia_tipo = :filtro_deficiencia")
        parametros["filtro_deficiencia"] = tipo
    sufixo = "".join(f" AND {clausula}" for clausula in clausulas)
    return sufixo, parametros


def cabecalho(titulo, subtitulo):
    st.markdown(
        f"""
        <div class="page-heading">
          <h1>{titulo}</h1>
          <span class="status-pill">CNES/Censo reais · PEC simulado</span>
        </div>
        <div class="small-muted" style="margin-top:-12px;margin-bottom:14px">
          {subtitulo}
        </div>
        """,
        unsafe_allow_html=True,
    )


def pagina_equidade():
    cabecalho(
        "Painel de Equidade em Saúde — Recife",
        "Acompanhamento territorial e completude do cadastro na Atenção Básica.",
    )
    st.markdown('<div class="filter-title">Filtros do painel</div>', unsafe_allow_html=True)
    renderizar_filtros()
    st.markdown(
        '<div class="notice">Dados de atendimentos e população por distrito '
        'são fictícios e servem somente para demonstração. Os dados territoriais '
        'e do Censo são públicos.</div>',
        unsafe_allow_html=True,
    )
    filtro, parametros = filtro_mock()
    kpis = consultar(
        f"""
        SELECT COUNT(*) AS atendimentos,
               COUNT(DISTINCT codigo_equipe) AS equipes,
               COUNT(DISTINCT distrito_sanitario_codigo) AS distritos,
               ROUND((
                   COALESCE(COUNT(raca_cor)::numeric / NULLIF(COUNT(*), 0), 0)
                   + COALESCE(COUNT(deficiencia_tipo)::numeric / NULLIF(COUNT(*), 0), 0)
                   + COALESCE(
                       (COUNT(deseja_informar_orientacao_sexual)
                           FILTER (WHERE idade >= 10))::numeric
                       / NULLIF(COUNT(*) FILTER (WHERE idade >= 10), 0), 0
                   )
                   + COALESCE(
                       (COUNT(deseja_informar_identidade_genero)
                           FILTER (WHERE idade >= 10))::numeric
                       / NULLIF(COUNT(*) FILTER (WHERE idade >= 10), 0), 0
                   )
               ) * 25, 1) AS preenchimento_medio
        FROM mock_pec_atendimentos a
        WHERE 1=1 {filtro}
        """,
        parametros,
    )
    kpi = kpis.iloc[0]
    metricas = st.columns(4)
    metricas[0].metric("Total de atendimentos", f"{int(kpi['atendimentos']):,}".replace(",", "."))
    metricas[1].metric("Equipes monitoradas", int(kpi["equipes"]))
    metricas[2].metric("Distritos cobertos", int(kpi["distritos"]))
    media = float(kpi["preenchimento_medio"] or 0)
    metricas[3].metric(
        "Preenchimento médio",
        f"{media:.1f}%".replace(".", ","),
        delta=f"{media - 90:.1f} p.p. vs. meta de 90%".replace(".", ","),
        delta_color="normal" if media >= 90 else "inverse",
    )

    st.write("")
    coluna_mapa, coluna_completude = st.columns([1.2, 1])
    with coluna_mapa:
        with st.container(border=True):
            df_mapa = consultar(
                f"""
                SELECT CAST(a.distrito_sanitario_codigo AS INTEGER) AS cdistscodi,
                       COUNT(*) FILTER (
                           WHERE (
                               a.orientacao_sexual IS NOT NULL
                               AND a.orientacao_sexual != 'Heterossexual'
                           ) OR a.identidade_genero IN
                               ('Mulher trans', 'Homem trans', 'Não-binário')
                       ) AS total
                FROM mock_pec_atendimentos a
                WHERE 1=1 {filtro}
                GROUP BY a.distrito_sanitario_codigo
                ORDER BY a.distrito_sanitario_codigo
                """,
                parametros,
            )
            mapa = mapa_distrito(
                df_mapa,
                "total",
                "Distribuição espacial — concentração LGBTQIAPN+",
                rotulo_valor="Atendimentos registrados",
            )
            st_folium(
                mapa,
                width=None,
                height=300,
                returned_objects=[],
                key="mapa_equidade_lgbt",
            )
    with coluna_completude:
        with st.container(border=True):
            st.markdown("**Preenchimento por campo sensível**")
            dados = consultar(
                f"""
                SELECT
                  ROUND(COUNT(a.raca_cor)::numeric / NULLIF(COUNT(*), 0) * 100, 1)
                    AS raca_cor,
                  ROUND(COUNT(a.deficiencia_tipo)::numeric / NULLIF(COUNT(*), 0) * 100, 1)
                    AS deficiencia,
                  ROUND(
                    (COUNT(a.deseja_informar_orientacao_sexual)
                        FILTER (WHERE a.idade >= 10))::numeric
                    / NULLIF(COUNT(*) FILTER (WHERE a.idade >= 10), 0) * 100, 1
                  ) AS orientacao,
                  ROUND(
                    (COUNT(a.deseja_informar_identidade_genero)
                        FILTER (WHERE a.idade >= 10))::numeric
                    / NULLIF(COUNT(*) FILTER (WHERE a.idade >= 10), 0) * 100, 1
                  ) AS genero
                FROM mock_pec_atendimentos a
                WHERE 1=1 {filtro}
                """,
                parametros,
            ).iloc[0]
            for coluna, rotulo in [
                ("raca_cor", "Raça/Cor"),
                ("deficiencia", "Deficiência"),
                ("orientacao", "Orient. Sexual — pessoas com 10+"),
                ("genero", "Ident. Gênero — pessoas com 10+"),
            ]:
                renderizar_progresso(rotulo, dados[coluna])
            st.caption("A regra do projeto exclui menores de 10 anos da análise LGBTQIAPN+.")

    with st.container(border=True):
        st.markdown("**Equipes de Saúde — menor preenchimento primeiro**")
        equipes = consultar(
            f"""
            SELECT a.codigo_equipe AS "Equipe",
                   a.distrito_sanitario_codigo AS "Código do Distrito",
                   COUNT(*) AS "Atendimentos",
                   ROUND(
                     (COUNT(a.deseja_informar_orientacao_sexual)
                         FILTER (WHERE a.idade >= 10))::numeric
                     / NULLIF(COUNT(*) FILTER (WHERE a.idade >= 10), 0) * 100, 1
                   ) AS "Preenchimento (%)"
            FROM mock_pec_atendimentos a
            WHERE a.profissional_tipo = 'ACS'
              AND a.data_atendimento >
                  (SELECT MAX(data_atendimento) FROM mock_pec_atendimentos)
                  - INTERVAL '3 months'
              {filtro}
            GROUP BY a.codigo_equipe, a.distrito_sanitario_codigo
            ORDER BY "Preenchimento (%)" ASC NULLS FIRST
            LIMIT 15
            """,
            parametros,
        )
        if not equipes.empty:
            equipes["Distrito"] = equipes["Código do Distrito"].map(rotulo_distrito)
            equipes = equipes[
                ["Equipe", "Distrito", "Atendimentos", "Preenchimento (%)"]
            ]
        st.dataframe(
            equipes,
            width="stretch",
            hide_index=True,
            column_config={
                "Preenchimento (%)": st.column_config.ProgressColumn(
                    "Preenchimento",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                )
            },
        )

    st.subheader("Outros indicadores territoriais")
    pcd_coluna, gap_coluna = st.columns(2)
    with pcd_coluna:
        with st.container(border=True):
            filtros, params_pcd = filtro_mock()
            tipo = st.session_state.get("filtro_deficiencia", "Todos os tipos")
            if tipo == "Todos os tipos":
                consulta_pcd = """
                    COUNT(*) FILTER (
                        WHERE a.deficiencia_tipo IS NOT NULL
                          AND a.deficiencia_tipo != 'Nenhuma'
                    )
                """
            else:
                consulta_pcd = "COUNT(*) FILTER (WHERE a.deficiencia_tipo = :tipo_pcd)"
                params_pcd["tipo_pcd"] = tipo
            pcd = consultar(
                f"""
                SELECT CAST(a.distrito_sanitario_codigo AS INTEGER) AS cdistscodi,
                       {consulta_pcd} AS total
                FROM mock_pec_atendimentos a
                WHERE 1=1 {filtros}
                GROUP BY a.distrito_sanitario_codigo
                ORDER BY a.distrito_sanitario_codigo
                """,
                params_pcd,
            )
            pcd_mapa = mapa_distrito(
                pcd,
                "total",
                f"Concentração PCD — {ROTULOS_DEFICIENCIA.get(tipo, tipo)}",
                rotulo_valor="Atendimentos registrados",
            )
            st_folium(
                pcd_mapa,
                width=None,
                height=300,
                returned_objects=[],
                key="mapa_equidade_pcd",
            )
    with gap_coluna:
        with st.container(border=True):
            gap = consultar(
                f"""
                SELECT CAST(a.distrito_sanitario_codigo AS INTEGER) AS cdistscodi,
                       ROUND(
                         p.populacao_negra_pct_esperado * 100
                         - COUNT(*) FILTER (
                             WHERE a.raca_cor IN ('Preta', 'Parda')
                           )::numeric
                           / NULLIF(COUNT(a.raca_cor), 0) * 100, 1
                       ) AS gap_pp
                FROM mock_pec_atendimentos a
                JOIN mock_populacao_negra_distrito p
                  ON p.distrito_sanitario_codigo = a.distrito_sanitario_codigo
                WHERE 1=1 {filtro}
                GROUP BY a.distrito_sanitario_codigo, p.populacao_negra_pct_esperado
                ORDER BY a.distrito_sanitario_codigo
                """,
                parametros,
            )
            gap_mapa = mapa_distrito(
                gap,
                "gap_pp",
                "População negra — esperado x observado",
                escala="OrRd",
                rotulo_valor="Diferença (p.p.)",
            )
            st_folium(
                gap_mapa,
                width=None,
                height=300,
                returned_objects=[],
                key="mapa_equidade_gap",
            )
            st.caption(
                "A referência por distrito é ilustrativa; não é uma estimativa "
                "oficial do Censo nesse nível territorial."
            )


def pagina_monitor():
    cabecalho(
        "Monitor de Qualidade do Cadastro — PEC/e-SUS",
        "Indicadores de completude, deficiência e orientação sexual.",
    )
    st.markdown(
        '<div class="notice">Dados simulados. Os filtros abaixo também afetam '
        'as tabelas e os gráficos desta página.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="filter-title">Filtros do painel</div>', unsafe_allow_html=True)
    renderizar_filtros()
    filtro, parametros = filtro_mock()

    ranking, evolucao = st.columns([1, 1.25])
    with ranking:
        with st.container(border=True):
            st.markdown("**Ranking: pior preenchimento por equipe**")
            df = consultar(
                f"""
                SELECT a.codigo_equipe AS "Equipe",
                       a.distrito_sanitario_codigo AS "Código do Distrito",
                       COUNT(*) AS "Atendimentos",
                       ROUND(
                         (COUNT(a.deseja_informar_orientacao_sexual)
                             FILTER (WHERE a.idade >= 10))::numeric
                         / NULLIF(COUNT(*) FILTER (WHERE a.idade >= 10), 0) * 100, 1
                       ) AS "Preenchimento (%)"
                FROM mock_pec_atendimentos a
                WHERE a.profissional_tipo = 'ACS'
                  AND a.data_atendimento >
                      (SELECT MAX(data_atendimento) FROM mock_pec_atendimentos)
                      - INTERVAL '3 months'
                  {filtro}
                GROUP BY a.codigo_equipe, a.distrito_sanitario_codigo
                ORDER BY "Preenchimento (%)" ASC NULLS FIRST
                LIMIT 10
                """,
                parametros,
            )
            if not df.empty:
                df["Distrito"] = df["Código do Distrito"].map(rotulo_distrito)
                df = df[["Equipe", "Distrito", "Atendimentos", "Preenchimento (%)"]]
            st.dataframe(
                df,
                width="stretch",
                hide_index=True,
                column_config={
                    "Preenchimento (%)": st.column_config.ProgressColumn(
                        "Preenchimento", min_value=0, max_value=100, format="%.1f%%"
                    )
                },
            )
    with evolucao:
        with st.container(border=True):
            st.markdown("**Evolução do preenchimento**")
            df = consultar(
                f"""
                SELECT DATE_TRUNC('month', a.data_atendimento) AS mes,
                       ROUND(
                         COUNT(a.raca_cor)::numeric / NULLIF(COUNT(*), 0) * 100, 1
                       ) AS "Raça/Cor",
                       ROUND(
                         COUNT(a.deficiencia_tipo)::numeric
                         / NULLIF(COUNT(*), 0) * 100, 1
                       ) AS "Deficiência",
                       ROUND(
                         (COUNT(a.deseja_informar_orientacao_sexual)
                             FILTER (WHERE a.idade >= 10))::numeric
                         / NULLIF(COUNT(*) FILTER (WHERE a.idade >= 10), 0) * 100, 1
                       ) AS "Orientação Sexual"
                FROM mock_pec_atendimentos a
                WHERE 1=1 {filtro}
                GROUP BY mes
                ORDER BY mes
                """,
                parametros,
            )
            if not df.empty:
                dados_linha = df.melt(
                    id_vars="mes",
                    var_name="Campo",
                    value_name="Preenchimento (%)",
                )
                st.plotly_chart(
                    preparar_grafico(
                        px.line(
                            dados_linha,
                            x="mes",
                            y="Preenchimento (%)",
                            color="Campo",
                            markers=True,
                            color_discrete_map={
                                "Raça/Cor": "#8051c5",
                                "Deficiência": "#46a77b",
                                "Orientação Sexual": "#e29a54",
                            },
                            labels={"mes": "Mês"},
                        ),
                        280,
                    ),
                    width="stretch",
                )
                st.caption(
                    "Deficiência considera campo preenchido, incluindo a resposta "
                    "“Nenhuma”; não representa somente pessoas com deficiência."
                )
            else:
                st.info("Sem registros para os filtros selecionados.")

    distribuicao, inconsistencias = st.columns([1.15, 1])
    with distribuicao:
        with st.container(border=True):
            st.markdown("**Distribuição de raça/cor por distrito**")
            df = consultar(
                f"""
                SELECT a.distrito_sanitario_codigo AS distrito,
                       a.raca_cor,
                       COUNT(*) AS total
                FROM mock_pec_atendimentos a
                WHERE a.raca_cor IS NOT NULL {filtro}
                GROUP BY a.distrito_sanitario_codigo, a.raca_cor
                ORDER BY a.distrito_sanitario_codigo, a.raca_cor
                """,
                parametros,
            )
            if not df.empty:
                df["distrito"] = df["distrito"].map(rotulo_distrito)
                fig = px.bar(
                    df,
                    x="distrito",
                    y="total",
                    color="raca_cor",
                    barmode="group",
                    color_discrete_map=CORES_RACA_COR,
                    category_orders={
                        "raca_cor": ["Branca", "Preta", "Parda", "Amarela", "Indígena"]
                    },
                    labels={
                        "distrito": "Distrito",
                        "total": "Atendimentos",
                        "raca_cor": "Raça/Cor",
                    },
                )
                st.plotly_chart(
                    preparar_grafico(fig, 300), width="stretch"
                )
            else:
                st.info("Sem registros para os filtros selecionados.")
    with inconsistencias:
        with st.container(border=True):
            st.markdown("**Inconsistências — orientação sexual**")
            df = consultar(
                f"""
                SELECT
                  COUNT(*) FILTER (
                    WHERE a.deseja_informar_orientacao_sexual IS NULL
                  ) AS "Campo em branco",
                  COUNT(*) FILTER (
                    WHERE a.deseja_informar_orientacao_sexual = 'Não'
                  ) AS "Recusou informar",
                  COUNT(*) FILTER (
                    WHERE a.deseja_informar_orientacao_sexual = 'Sim'
                  ) AS "Informou"
                FROM mock_pec_atendimentos a
                WHERE a.idade >= 10 {filtro}
                """,
                parametros,
            )
            df_long = df.melt(var_name="Categoria", value_name="Atendimentos")
            fig = px.bar(
                df_long,
                x="Categoria",
                y="Atendimentos",
                color="Categoria",
                color_discrete_map=CORES_INCONSISTENCIA,
                category_orders={"Categoria": ORDEM_INCONSISTENCIA},
            )
            st.plotly_chart(
                preparar_grafico(fig.update_layout(showlegend=False), 300),
                width="stretch",
            )
            st.caption("A faixa etária segue a regra de análise definida para o projeto.")

    with st.container(border=True):
        st.markdown("**Atendimentos com deficiência registrados por distrito**")
        df = consultar(
            f"""
            SELECT a.distrito_sanitario_codigo AS distrito,
                   a.deficiencia_tipo AS tipo_deficiencia,
                   COUNT(*) AS atendimentos
            FROM mock_pec_atendimentos a
            WHERE a.deficiencia_tipo IS NOT NULL
              AND a.deficiencia_tipo != 'Nenhuma'
              {filtro}
            GROUP BY a.distrito_sanitario_codigo, a.deficiencia_tipo
            ORDER BY a.distrito_sanitario_codigo, atendimentos DESC
            """,
            parametros,
        )
        if not df.empty:
            df["distrito"] = df["distrito"].map(rotulo_distrito)
            df["tipo_deficiencia"] = df["tipo_deficiencia"].map(
                lambda valor: ROTULOS_DEFICIENCIA.get(valor, valor)
            )
            fig = px.bar(
                df,
                x="distrito",
                y="atendimentos",
                color="tipo_deficiencia",
                barmode="group",
                labels={
                    "distrito": "Distrito Sanitário",
                    "atendimentos": "Atendimentos registrados",
                    "tipo_deficiencia": "Tipo de deficiência",
                },
                color_discrete_sequence=PALETA,
            )
            st.plotly_chart(preparar_grafico(fig, 360), width="stretch")
        else:
            st.info(
                "Não há atendimentos com deficiência registrados para os filtros selecionados."
            )
        st.caption(
            "Dados simulados. A contagem representa atendimentos registrados, "
            "não pessoas únicas; registros sem deficiência e campos em branco "
            "não são incluídos."
        )


def pagina_contexto():
    cabecalho(
        "Contexto Territorial",
        "Estrutura de saúde e dados públicos do Censo Demográfico 2022.",
    )
    dados_municipio = carregar_contexto_macroregiao_recife()
    resumo_cnes = carregar_resumo_estabelecimentos_cnes_recife()
    unidades = consultar("SELECT COUNT(*) AS total FROM unidades_saude").iloc[0]["total"]
    equipes = consultar("SELECT COUNT(*) AS total FROM equipes_saude").iloc[0]["total"]
    unidades_distrito = consultar(
        """
        SELECT COUNT(*) AS total FROM unidades_saude
        WHERE distrito_sanitario_codigo IS NOT NULL
        """
    ).iloc[0]["total"]
    cobertura = st.columns(4)
    cobertura[0].metric(
        "Estabelecimentos CNES em Recife",
        f"{resumo_cnes['total']:,}".replace(",", "."),
    )
    cobertura[1].metric(
        "Estabelecimentos que atendem SUS",
        f"{resumo_cnes['atendem_sus']:,}".replace(",", "."),
    )
    cobertura[2].metric(
        "Equipes cadastradas",
        f"{int(equipes):,}".replace(",", "."),
    )
    cobertura[3].metric(
        "População de Recife (IBGE 2022)",
        f"{int(dados_municipio['populacao_ibge_2022']):,}".replace(",", "."),
    )
    st.caption(
        f"Recife pertence à {dados_municipio['regiao_de_saude']} — "
        f"Macrorregião {dados_municipio['macrorregiao_de_saude']}. "
        "O arquivo de macrorregiões informa população e região, não lista "
        "estabelecimentos; os totais de unidades vêm do CNES."
    )
    st.caption(
        f"A tabela detalhada do Neon contém {int(unidades):,} unidades; "
        f"{int(unidades_distrito):,} têm distrito informado."
    )
    if int(unidades) != resumo_cnes["atendem_sus"]:
        st.warning(
            "A quantidade de unidades detalhadas no Neon diverge do total "
            "CNES de estabelecimentos que atendem SUS. Confira a atualização "
            "da carga antes de comparar esses números."
        )

    unidades_mapeadas = carregar_unidades_geograficas()
    unidades_cadastradas = carregar_unidades_cadastradas()
    farmacias_populares = carregar_farmacias_populares()
    percentuais_distritos = carregar_percentuais_populacao_distrito()
    geojson_distritos = carregar_geojson()
    st.subheader("Mapa interativo — unidades e Distritos Sanitários")
    with st.container(border=True):
        distrito_selecionado = st.selectbox(
            "Filtrar unidades por distrito",
            ["Todos", *DISTRITOS],
            format_func=lambda codigo: (
                "Todos os distritos"
                if codigo == "Todos"
                else rotulo_distrito(codigo)
            ),
            key="mapa_distrito_unidades",
        )
        unidades_visiveis = (
            unidades_mapeadas
            if distrito_selecionado == "Todos"
            else unidades_mapeadas[
                unidades_mapeadas["distrito_mapa"] == distrito_selecionado
            ]
        )
        coordenadas_validas = int(
            unidades_visiveis["coordenada_dentro_distrito"].sum()
        )
        coordenadas_aproximadas = int(
            (
                ~unidades_visiveis["coordenada_dentro_distrito"]
                & unidades_visiveis["distrito_mapa"].notna()
            ).sum()
        )
        coordenadas_sem_distrito = int(
            (
                ~unidades_visiveis["coordenada_dentro_distrito"]
                & unidades_visiveis["distrito_mapa"].isna()
            ).sum()
        )
        st.caption(
            f"{coordenadas_validas:,} unidades aparecem nas coordenadas "
            f"cadastradas; {coordenadas_aproximadas:,} com coordenadas fora "
            "dos limites são indicadas em posição aproximada no distrito "
            f"informado. {coordenadas_sem_distrito:,} sem distrito confiável "
            "não são exibidas no mapa. Passe o mouse sobre um distrito para "
            "ver percentuais estimados e totais, ou clique nele para abrir "
            "a relação de unidades cadastradas e farmácias associadas à área."
        )
        st.caption(
            "A simulação preserva os totais municipais de 60,8% de pessoas "
            "negras (48,5% pardas + 12,3% pretas), 11,1% de PCD e 4% "
            "LGBTQIA+ sobre o público estimado da Atenção Básica (80% da "
            "população). A distribuição por distrito prioriza áreas mais "
            "distantes do litoral e do centro, por aproximação geográfica, "
            "com fator ilustrativo de 0,8 a 1,2. O hover mostra o percentual "
            "estimado dentro de cada distrito; para LGBTQIA+, o denominador "
            "é a população estimada da Atenção Básica local. Não são dados "
            "oficiais por distrito."
        )
        st.caption(
            f"{len(farmacias_populares):,} farmácias da planilha anexada, "
            "associadas aos distritos pelo bairro. A planilha não contém "
            "coordenadas; os marcadores laranja indicam o distrito, não o "
            "endereço exato."
        )
        st_folium(
            mapa_unidades_saude(
                unidades_mapeadas,
                geojson_distritos,
                distrito_selecionado,
                farmacias_populares,
                unidades_cadastradas,
                percentuais_distritos,
            ),
            width=None,
            height=560,
            returned_objects=[],
            key="mapa_unidades_saude_recife",
        )
        sem_coordenadas = int(unidades) - len(unidades_mapeadas)
        if sem_coordenadas:
            st.caption(
                f"{sem_coordenadas:,} unidades não aparecem como marcadores "
                "por não terem latitude e longitude. Se também não tiverem "
                "distrito cadastrado, não podem ser atribuídas à lista de um distrito."
            )
        sem_distrito_mapeado = int(
            unidades_mapeadas["distrito_mapa"].isna().sum()
        )
        if sem_distrito_mapeado:
            st.caption(
                f"{sem_distrito_mapeado:,} unidade com coordenadas não foi "
                "associada a um distrito e aparece somente como marcador."
            )

    censo = carregar_indicadores_censo()
    st.subheader(f"Percentuais da população — Censo Demográfico {censo['ano']}")
    with st.container(border=True):
        negra, pcd, lgbt = st.columns(3)
        negra.metric(
            "População negra (Preta + Parda)",
            f"{censo['percentual_negra']:.1f}%".replace(".", ","),
            help=(
                f"{censo['populacao_negra']:,} pessoas pretas ou pardas de "
                f"{censo['populacao_total']:,} residentes. Fórmula: "
                "(Preta + Parda) / população residente total."
            ).replace(",", "."),
        )
        pcd.metric(
            "Deficiência — pessoas com 2+ anos",
            f"{censo['percentual_com_deficiencia']:.1f}%".replace(".", ","),
            help=(
                f"{censo['populacao_com_deficiencia']:,} pessoas com deficiência "
                f"de {censo['populacao_referencia_deficiencia']:,} pessoas "
                "com 2 anos ou mais. Fórmula: total oficial com deficiência / "
                "população de 2 anos ou mais."
            ).replace(",", "."),
        )
        estimativa_lgbtqia = estimar_populacao_lgbtqia(
            int(dados_municipio["populacao_ibge_2022"]),
            PERCENTUAL_REFERENCIA_LGBTQIA,
        )
        estimativa_com_base_censo = estimar_populacao_lgbtqia(
            censo["populacao_total"],
            PERCENTUAL_REFERENCIA_LGBTQIA,
        )
        lgbt.metric(
            "Estimativa LGBTQIA+ (referência de 4%)",
            f"≈ {estimativa_lgbtqia:,}".replace(",", "."),
            help=(
                f"Estimativa ilustrativa: "
                f"{int(dados_municipio['populacao_ibge_2022']):,} habitantes × "
                f"{PERCENTUAL_REFERENCIA_LGBTQIA:.0%} = "
                f"{int(dados_municipio['populacao_ibge_2022']) * PERCENTUAL_REFERENCIA_LGBTQIA:,.2f} "
                f"(aproximadamente {estimativa_lgbtqia:,} pessoas). "
                "A taxa de 4% é uma hipótese de referência; não é uma "
                "contagem observada pelo Censo."
            ).replace(",", "."),
        )
        texto_estimativa = (
            "Estimativa ilustrativa, não contagem oficial: usa a população-base "
            f"{int(dados_municipio['populacao_ibge_2022']):,} do arquivo de "
            "macrorregiões de saúde e a taxa de referência de 4%. "
            f"O arquivo do Censo 2022 usado neste projeto informa "
            f"{censo['populacao_total']:,} residentes; aplicando a mesma taxa, "
            f"o resultado seria aproximadamente {estimativa_com_base_censo:,} pessoas."
        )
        st.caption(texto_estimativa.replace(",", "."))
        if int(dados_municipio["populacao_ibge_2022"]) != censo["populacao_total"]:
            st.warning(
                "A população do arquivo de macrorregiões diverge do total do "
                "Censo usado nos indicadores. Confira as fontes antes de comparar."
            )
        st.caption(
            "Fonte para raça/cor e deficiência: IBGE, Censo Demográfico 2022. "
            "A população municipal também foi conferida no arquivo de "
            "macrorregiões de saúde (código IBGE 261160). "
            "O percentual de deficiência usa a população residente de 2 anos ou "
            "mais como denominador. A taxa LGBTQIA+ de 4% é uma hipótese de "
            "referência, não um resultado medido pelo Censo ou pelo mock. "
            "Para planejamento de Atenção Básica, também pode ser usado um "
            "cenário operacional com 80% da população municipal em atenção, "
            "11,1% de deficiência, 48,5% de pardos, 12,3% de pretos, "
            "60,8% de negros (pretos + pardos), 38,8% de brancos e o restante "
            "em indígenas/ amarelos; nesse cenário, 4% do público de atenção "
            "equivale à população LGBTQIA+ referenciada."
        )

    col_unidades, col_tipos = st.columns(2)
    with col_unidades:
        with st.container(border=True):
            st.markdown("**Unidades por Distrito Sanitário**")
            df = consultar(
                """
                SELECT distrito_sanitario_nome, COUNT(*) AS total
                FROM unidades_saude
                WHERE distrito_sanitario_codigo IS NOT NULL
                GROUP BY distrito_sanitario_nome
                ORDER BY distrito_sanitario_nome
                """
            )
            fig = px.bar(
                df,
                x="distrito_sanitario_nome",
                y="total",
                color_discrete_sequence=["#8051c5"],
                labels={
                    "distrito_sanitario_nome": "Distrito Sanitário",
                    "total": "Unidades",
                },
            )
            st.plotly_chart(
                preparar_grafico(fig, 300), width="stretch"
            )
    with col_tipos:
        with st.container(border=True):
            st.markdown("**Equipes por tipo**")
            df = consultar(
                """
                SELECT tipo_equipe, COUNT(*) AS total
                FROM equipes_saude
                GROUP BY tipo_equipe
                ORDER BY total DESC
                """
            )
            fig = px.bar(
                df,
                x="tipo_equipe",
                y="total",
                color_discrete_sequence=["#9c78cb"],
                labels={"tipo_equipe": "Tipo de equipe", "total": "Equipes"},
            )
            st.plotly_chart(
                preparar_grafico(fig, 300), width="stretch"
            )

    raca, deficiencia = st.columns(2)
    with raca:
        with st.container(border=True):
            st.markdown("**População por raça/cor — Censo 2022**")
            df = consultar(
                "SELECT raca_cor, populacao FROM censo_raca_cor "
                "ORDER BY populacao DESC"
            )
            fig = px.bar(
                df,
                x="raca_cor",
                y="populacao",
                color="raca_cor",
                color_discrete_map=CORES_RACA_COR,
                labels={"raca_cor": "Raça/Cor", "populacao": "População"},
            )
            st.plotly_chart(
                preparar_grafico(fig.update_layout(showlegend=False), 300),
                width="stretch",
            )
    with deficiencia:
        with st.container(border=True):
            st.markdown("**População por tipo de deficiência — Censo 2022**")
            df = consultar(
                """
                SELECT tipo_dificuldade, populacao FROM censo_deficiencia
                WHERE e_total = false ORDER BY populacao DESC
                """
            )
            if not df.empty:
                df["tipo_dificuldade"] = df["tipo_dificuldade"].map(
                    lambda valor: ROTULOS_DEFICIENCIA.get(valor, valor)
                )
            fig = px.bar(
                df,
                y="tipo_dificuldade",
                x="populacao",
                orientation="h",
                color_discrete_sequence=["#8051c5"],
                labels={
                    "tipo_dificuldade": "Tipo de dificuldade",
                    "populacao": "População",
                },
            )
            st.plotly_chart(
                preparar_grafico(fig, 300), width="stretch"
            )
            st.caption(
                "As categorias de dificuldade não são mutuamente exclusivas; "
                "não some esses valores para obter o total."
            )

    with st.container(border=True):
        st.markdown("**Unidades sem Distrito Sanitário preenchido**")
        df = consultar(
            """
            SELECT cnes, nome_fantasia, tipo_estabelecimento
            FROM unidades_saude
            WHERE distrito_sanitario_codigo IS NULL
            ORDER BY nome_fantasia
            """
        )
        st.dataframe(df, width="stretch", hide_index=True)


@st.cache_data(ttl=300)
def carregar_atendimentos_modelagem(campo):
    from src.ml.modelo_risco_preenchimento import CAMPOS_MONITORADOS

    if campo not in CAMPOS_MONITORADOS:
        raise ValueError(f"Campo monitorado inválido: {campo}.")
    coluna_alvo, coluna_status = CAMPOS_MONITORADOS[campo]
    colunas = [
        "codigo_equipe",
        "distrito_sanitario_codigo",
        "data_atendimento",
        "tipo_atendimento",
        "profissional_tipo",
        "turno_atendimento",
        "idade",
        coluna_alvo,
    ]
    if coluna_status is not None:
        colunas.append(coluna_status)
    return consultar(
        f"SELECT {', '.join(colunas)} FROM mock_pec_atendimentos "
        "WHERE codigo_equipe IS NOT NULL AND data_atendimento IS NOT NULL "
        "ORDER BY data_atendimento"
    )


@st.cache_data(ttl=900, show_spinner=False)
def calcular_risco_modelo(atendimentos, campo):
    from src.ml.modelo_risco_preenchimento import treinar_e_prever

    return treinar_e_prever(atendimentos, campo)


def pagina_insights_ml():
    from src.ml.modelo_risco_preenchimento import CAMPOS_MONITORADOS

    cabecalho(
        "Painel de Insights — Machine Learning",
        "Risco estimado de não preenchimento por equipe, com validação temporal.",
    )
    st.markdown(
        '<div class="notice">Demonstração com atendimentos fictícios. '
        "As probabilidades e métricas abaixo não representam desempenho real "
        "nem devem ser usadas para avaliar profissionais ou pressionar pacientes. "
        "Uma recusa informada é considerada resposta válida. Para raça/cor e "
        "deficiência, a base não distingue recusa de campo não perguntado.</div>",
        unsafe_allow_html=True,
    )

    campo = st.selectbox(
        "Campo monitorado",
        list(CAMPOS_MONITORADOS),
        index=list(CAMPOS_MONITORADOS).index("Orientação Sexual"),
        key="ml_campo",
    )
    try:
        atendimentos = carregar_atendimentos_modelagem(campo)
    except SQLAlchemyError as erro:
        st.error(
            "Não foi possível ler os atendimentos do Neon. Confirme a conexão "
            "e o schema; se faltar `turno_atendimento`, siga o procedimento do README "
            "para gerar e carregar o mock atualizado."
        )
        st.exception(erro)
        return

    seletores = st.columns([1, 1], gap="medium")
    with seletores[0]:
        distritos = sorted(
            atendimentos["distrito_sanitario_codigo"].dropna().astype(str).unique()
        )
        distrito_selecionado = st.selectbox(
            "Distrito Sanitário",
            ["Todos"] + distritos,
            format_func=lambda valor: (
                "Todos" if valor == "Todos" else rotulo_distrito(valor)
            ),
            key="ml_distrito",
        )
    with seletores[1]:
        equipes = sorted(atendimentos["codigo_equipe"].dropna().astype(str).unique())
        equipe_selecionada = st.selectbox(
            "Equipe de Saúde",
            ["Todas"] + equipes,
            key="ml_equipe",
        )
    try:
        with st.spinner("Treinando e avaliando a regressão logística..."):
            resultado = calcular_risco_modelo(atendimentos, campo)
    except ValueError as erro:
        st.warning(str(erro))
        st.info(
            "Para incluir a variável turno, gere novamente os atendimentos "
            "simulados e execute a carga no MongoDB e a transformação para o Neon."
        )
        return

    ranking = resultado["ranking"].copy()
    ranking["distrito_sanitario_codigo"] = (
        ranking["distrito_sanitario_codigo"].astype(str)
    )
    if distrito_selecionado != "Todos":
        ranking = ranking[
            ranking["distrito_sanitario_codigo"] == distrito_selecionado
        ]
    if equipe_selecionada != "Todas":
        ranking = ranking[ranking["codigo_equipe"] == equipe_selecionada]

    metricas = resultado["metricas"]
    limiar_alerta = 0.5
    equipes_alto_risco = int((ranking["risco_previsto"] >= limiar_alerta).sum())
    st.markdown(
        f'<div class="notice"><b>{equipes_alto_risco} equipe(s)</b> com risco '
        f'estimado alto (≥ {limiar_alerta:.0%}) entre os filtros selecionados. '
        "O alerta orienta revisão de processo e capacitação; não é avaliação individual.</div>",
        unsafe_allow_html=True,
    )

    metricas_colunas = st.columns(4, gap="medium")
    metricas_colunas[0].metric(
        "Equipes monitoradas",
        f"{ranking['codigo_equipe'].nunique():,}".replace(",", "."),
        help="Equipes com registros elegíveis no último mês simulado.",
    )
    metricas_colunas[1].metric(
        "Risco médio previsto",
        f"{ranking['risco_previsto'].mean():.1%}" if not ranking.empty else "—",
        help=(
            "Média das probabilidades por equipe para o período seguinte, "
            "usando o perfil de atendimentos mais recente como referência."
        ),
    )
    metricas_colunas[2].metric(
        "Acurácia temporal",
        f"{metricas['acuracia']:.1%}",
        help=(
            f"Treino: {metricas['mes_inicio_treino']} a "
            f"{metricas['mes_fim_treino']}; teste temporal: "
            f"{metricas['mes_inicio_teste']}. Métrica apenas dos dados simulados."
        ),
    )
    metricas_colunas[3].metric(
        "Atendimentos no treino (3 meses)",
        f"{metricas['n_treino']:,}".replace(",", "."),
        help=(
            f"Janela usada no treino: {metricas['mes_inicio_treino']} a "
            f"{metricas['mes_fim_treino']}. Há {resultado['total_elegivel']:,} "
            "registros elegíveis no histórico simulado completo."
        ),
    )
    auc = metricas["roc_auc"]
    legenda_auc = (
        f"Validação temporal simulada — ROC-AUC: {auc:.3f}"
        if auc is not None
        else "ROC-AUC indisponível"
    )
    legenda_validacao = (
        f"Precisão: {metricas['precisao']:.1%} · "
        f"Recall: {metricas['recall']:.1%} · "
        f"Treino/teste: {metricas['n_treino']:,}/{metricas['n_teste']:,} registros"
    ).replace(",", ".")
    st.caption(
        legenda_auc
    )
    st.caption(legenda_validacao)

    coluna_ranking, coluna_importancia = st.columns([1.1, 1])
    with coluna_ranking:
        with st.container(border=True):
            st.markdown("**Ranking de risco estimado por equipe**")
            st.caption(
                f"Perfil de referência: {resultado['mes_referencia']}. "
                "Risco agregado por equipe, não por paciente ou profissional."
            )
            if ranking.empty:
                st.info("Não há equipes para os filtros selecionados.")
            else:
                tabela = ranking.head(15).copy()
                tabela["Distrito"] = tabela[
                    "distrito_sanitario_codigo"
                ].map(rotulo_distrito)
                tabela["Risco estimado"] = tabela["risco_previsto"].map(
                    lambda valor: f"{valor:.0%}"
                )
                tabela = tabela.rename(
                    columns={
                        "codigo_equipe": "Equipe",
                        "atendimentos_referencia": "Atendimentos de referência",
                    }
                )
                st.dataframe(
                    tabela[
                        [
                            "Equipe",
                            "Distrito",
                            "Atendimentos de referência",
                            "Risco estimado",
                        ]
                    ],
                    width="stretch",
                    hide_index=True,
                )
    with coluna_importancia:
        with st.container(border=True):
            st.markdown("**Influência relativa das variáveis**")
            importancia = pd.DataFrame(
                [
                    {"Variável": nome, "Importância": valor}
                    for nome, valor in resultado["importancia"].items()
                ]
            ).sort_values("Importância", ascending=True)
            fig = px.bar(
                importancia,
                x="Importância",
                y="Variável",
                orientation="h",
                text=importancia["Importância"].map(lambda valor: f"{valor:.0%}"),
                labels={"Importância": "Magnitude relativa dos coeficientes"},
                color_discrete_sequence=["#5c249e"],
            )
            st.plotly_chart(
                preparar_grafico(fig, max(260, 45 * len(importancia))),
                width="stretch",
            )
            st.caption(
                "Magnitude dos coeficientes da regressão logística; não indica "
                "causalidade nem é uma medida de efeito de política pública."
            )

    st.markdown("### Como o modelo funciona")
    with st.container(border=True):
        explicacoes = st.columns(4, gap="small")
        textos = [
            (
                "PROBLEMA",
                "Estima a chance de um campo elegível terminar sem resposta "
                "registrada; não infere a razão da ausência.",
            ),
            (
                "ALGORITMO",
                "Classificação binária por regressão logística, com variáveis "
                "categóricas codificadas e histórico anterior da equipe. "
                "O treino usa uma janela móvel de três meses.",
            ),
            (
                "VALIDAÇÃO",
                "Treino nos três meses anteriores e teste no mês seguinte. "
                "Nenhum dado futuro entra no histórico.",
            ),
            (
                "USO",
                "Apoiar revisão do fluxo e capacitação. Resultados simulados não "
                "medem eficácia real; decisões permanecem com as equipes.",
            ),
        ]
        for coluna, (titulo, texto) in zip(explicacoes, textos):
            with coluna:
                st.markdown(
                    f'<div class="notice"><b>{titulo}</b><br>{texto}</div>',
                    unsafe_allow_html=True,
                )



def pagina_assistente():
    cabecalho(
        "Assistente EquiDados — IA",
        "Faça perguntas em português sobre os dados disponíveis no Neon.",
    )
    st.markdown(
        '<div class="notice">O assistente usa o Ollama local para gerar consultas. '
        'Respostas sobre tabelas <code>mock_</code> usam dados fictícios.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="chat-hint"><b>Experimente perguntar:</b><br>'
        'Quantas unidades existem no Distrito I? · Qual é o preenchimento de '
        'raça/cor? · Quais equipes têm menor completude?</div>',
        unsafe_allow_html=True,
    )
    if "historico_assistente" not in st.session_state:
        st.session_state["historico_assistente"] = []
    for mensagem in st.session_state["historico_assistente"]:
        with st.chat_message(mensagem["role"]):
            st.markdown(mensagem["content"])

    pergunta = st.chat_input("Digite sua pergunta sobre os dados...")
    if pergunta:
        st.session_state["historico_assistente"].append(
            {"role": "user", "content": pergunta}
        )
        with st.chat_message("user"):
            st.markdown(pergunta)
        with st.chat_message("assistant"):
            with st.spinner("Consultando o assistente local e o banco..."):
                try:
                    from src.agent.assistente import responder_pergunta

                    resposta = responder_pergunta(pergunta)
                    st.markdown(resposta)
                    st.session_state["historico_assistente"].append(
                        {"role": "assistant", "content": resposta}
                    )
                except Exception as erro:
                    st.error(f"Não foi possível responder: {erro}")


try:
    obter_engine()
except RuntimeError as erro:
    st.error(str(erro))
    st.info(
        "Crie um arquivo .env na raiz do projeto e defina "
        "NEON_DATABASE_URL com a conexão do PostgreSQL."
    )
    st.stop()

with st.sidebar:
    st.markdown('<div class="brand-mark">E</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-name">EquiDados</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="brand-subtitle">Equidade em Saúde — Recife</div>',
        unsafe_allow_html=True,
    )
    pagina = st.radio(
        "Navegação",
        list(PAGINAS),
        format_func=lambda valor: f"{PAGINAS[valor]}  {valor}",
        label_visibility="collapsed",
        key="navegacao_equidados",
    )
    st.markdown(
        '<div class="sidebar-note">Atenção Básica · Recife<br>'
        "Dados de demonstração identificados.</div>",
        unsafe_allow_html=True,
    )

if pagina == "Painel de Equidade":
    pagina_equidade()
elif pagina == "Monitor de Cadastro":
    pagina_monitor()
elif pagina == "Contexto Territorial":
    pagina_contexto()
elif pagina == "Insights de ML":
    pagina_insights_ml()
elif pagina == "Dados e consultas SQL":
    from src.dashboard.pagina_dados import pagina_dados

    pagina_dados(consultar, obter_engine)
else:
    pagina_assistente()
