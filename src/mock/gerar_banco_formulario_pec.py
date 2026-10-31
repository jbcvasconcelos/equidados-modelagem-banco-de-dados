"""
Gera uma base SQLite de formularios individuais sinteticos inspirados na
Ficha de Cadastro Individual do PEC/e-SUS APS v5.31.

Os registros e enderecos sao ficticios. Os bairros e a relacao bairro-distrito
vêm do arquivo publico de bairros do Recife; os pesos populacionais distritais
e os percentuais sao premissas de planejamento, nao dados censitarios locais.
"""

import argparse
import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PASTA_DADOS = ROOT / "data" / "bronze" / "dados_recife"
PASTA_SAIDA = ROOT / "data" / "bronze" / "mock_pec"
ARQUIVO_DB = PASTA_SAIDA / "pec_formulario_recife.sqlite"

POPULACAO_RECIFE = 1_488_920
PERCENTUAL_ATENCAO_BASICA = 0.80
PERCENTUAL_DEFICIENCIA = 0.111
PERCENTUAL_LGBTQIA_ATENCAO_BASICA = 0.04
SEXO_POPULACAO_CENSO_2022 = {
    "M": 683_536,
    "F": 805_384,
    "I": 0,
}
TOTAL_CADASTROS_ATENCAO_BASICA = int(
    POPULACAO_RECIFE * PERCENTUAL_ATENCAO_BASICA + 0.5
)

# Distribuicao provisoria usada somente para demonstracao. Nao e estimativa
# oficial da populacao residente em cada Distrito Sanitario.
PESO_POPULACIONAL_DISTRITO = {
    "01": 0.14,
    "02": 0.12,
    "03": 0.11,
    "04": 0.12,
    "05": 0.15,
    "06": 0.11,
    "07": 0.13,
    "08": 0.12,
}

# 48,5% + 12,3% = 60,8%. O restante de 0,4% foi dividido igualmente,
# pois nao foi fornecida a distribuicao entre amarelos e indigenas.
PERCENTUAIS_RACA_COR = {
    "Branca": 0.388,
    "Preta": 0.123,
    "Parda": 0.485,
    "Amarela": 0.002,
    "Indígena": 0.002,
}

RACAS = list(PERCENTUAIS_RACA_COR)
TIPOS_DEFICIENCIA = [
    "Auditiva",
    "Intelectual/Cognitiva",
    "TEA",
    "Visual",
    "Física",
    "Outra",
]
ORIENTACOES_SEXUAIS = [
    "Heterossexual",
    "Gay",
    "Lésbica",
    "Bissexual",
    "Assexual",
    "Pansexual",
    "Outro",
]
IDENTIDADES_GENERO = [
    "Homem cisgênero",
    "Mulher cisgênero",
    "Homem transgênero",
    "Mulher transgênero",
    "Travesti",
    "Não-Binário",
    "Outro",
]
IDENTIDADES_LGBTQIA = [
    ("Gay", "Homem cisgênero"),
    ("Lésbica", "Mulher cisgênero"),
    ("Bissexual", "Homem cisgênero"),
    ("Assexual", "Mulher cisgênero"),
    ("Pansexual", "Não-Binário"),
    ("Heterossexual", "Homem transgênero"),
    ("Heterossexual", "Mulher transgênero"),
    ("Heterossexual", "Travesti"),
    ("Outro", "Outro"),
]
SEED = 42


def arredondar_por_pesos(total, pesos):
    """Distribui um total inteiro pelos pesos usando maiores restos."""
    soma_pesos = sum(pesos.values())
    if total < 0 or soma_pesos <= 0:
        raise ValueError("Total e pesos devem ser positivos.")

    quotas = {
        chave: total * peso / soma_pesos
        for chave, peso in pesos.items()
    }
    resultados = {chave: int(quota) for chave, quota in quotas.items()}
    faltantes = total - sum(resultados.values())
    ordem = sorted(
        quotas,
        key=lambda chave: (-(quotas[chave] - resultados[chave]), chave),
    )
    for chave in ordem[:faltantes]:
        resultados[chave] += 1
    return resultados


def arredondar_percentual(total, percentual):
    return int(total * percentual + 0.5)


def distribuir_categorias_por_distrito(totais_distritais, percentuais):
    total_amostra = sum(totais_distritais.values())
    metas_categoria = arredondar_por_pesos(total_amostra, percentuais)
    matriz = {
        distrito: arredondar_por_pesos(quantidade, percentuais)
        for distrito, quantidade in totais_distritais.items()
    }
    atuais_categoria = {
        categoria: sum(matriz[distrito][categoria] for distrito in matriz)
        for categoria in percentuais
    }

    while atuais_categoria != metas_categoria:
        categorias_faltantes = [
            categoria
            for categoria in percentuais
            if atuais_categoria[categoria] < metas_categoria[categoria]
        ]
        categorias_excedentes = [
            categoria
            for categoria in percentuais
            if atuais_categoria[categoria] > metas_categoria[categoria]
        ]
        destino = categorias_faltantes[0]
        origem = categorias_excedentes[0]
        distrito = next(
            distrito
            for distrito in matriz
            if matriz[distrito][origem] > 0
        )
        matriz[distrito][origem] -= 1
        matriz[distrito][destino] += 1
        atuais_categoria[origem] -= 1
        atuais_categoria[destino] += 1
    return matriz


def carregar_bairros_por_distrito():
    arquivos = sorted(PASTA_DADOS.glob("distritos_bairros_*.json"))
    if not arquivos:
        raise FileNotFoundError(
            f"Nao encontrei o mapeamento de bairros em {PASTA_DADOS}."
        )

    with arquivos[-1].open(encoding="utf-8") as arquivo:
        registros = json.load(arquivo)

    bairros = {codigo: [] for codigo in PESO_POPULACIONAL_DISTRITO}
    for registro in registros:
        codigo = str(registro["distrito_sanitario"]).zfill(2)
        if codigo in bairros:
            bairros[codigo].append(registro["bairro"])

    distritos_sem_bairro = [
        codigo for codigo, nomes in bairros.items() if not nomes
    ]
    if distritos_sem_bairro:
        raise ValueError(
            "O arquivo de bairros nao tem bairros para os distritos: "
            + ", ".join(distritos_sem_bairro)
        )
    return bairros, arquivos[-1].name


def gerar_data_nascimento(rng, idade):
    data_referencia = date(2026, 10, 21)
    data_inicial = data_referencia.replace(year=data_referencia.year - idade)
    dias = rng.randrange(365)
    try:
        return (data_inicial - timedelta(days=dias)).isoformat()
    except OverflowError:
        return data_inicial.isoformat()


def criar_esquema(cursor):
    # Estas tabelas sao de propriedade deste gerador e sao reconstruidas para
    # tornar a geracao deterministica; outras tabelas do arquivo sao mantidas.
    cursor.execute("DROP TABLE IF EXISTS cadastro_pec")
    cursor.execute("DROP TABLE IF EXISTS enderecos_por_distrito")
    cursor.execute("DROP TABLE IF EXISTS distrito_populacao")
    cursor.execute("DROP TABLE IF EXISTS metadados_simulacao")

    cursor.executescript(
        """
        CREATE TABLE metadados_simulacao (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );

        CREATE TABLE distrito_populacao (
            distrito_sanitario_codigo TEXT PRIMARY KEY,
            distrito_sanitario_nome TEXT NOT NULL,
            peso_populacional_simulado REAL NOT NULL,
            populacao_total_estimada INTEGER NOT NULL,
            populacao_atencao_basica_estimada INTEGER NOT NULL,
            populacao_feminina_estimada INTEGER NOT NULL,
            populacao_masculina_estimada INTEGER NOT NULL,
            populacao_sexo_ignorado_estimada INTEGER NOT NULL,
            populacao_feminina_atencao_basica_estimada INTEGER NOT NULL,
            populacao_masculina_atencao_basica_estimada INTEGER NOT NULL,
            populacao_sexo_ignorado_atencao_basica_estimada INTEGER NOT NULL,
            populacao_branca_estimada INTEGER NOT NULL,
            populacao_preta_estimada INTEGER NOT NULL,
            populacao_parda_estimada INTEGER NOT NULL,
            populacao_amarela_estimada INTEGER NOT NULL,
            populacao_indigena_estimada INTEGER NOT NULL,
            populacao_negra_estimada INTEGER NOT NULL,
            populacao_com_deficiencia_estimada INTEGER NOT NULL,
            populacao_com_deficiencia_atencao_basica_estimada INTEGER NOT NULL,
            populacao_lgbtqia_atencao_basica_estimada INTEGER NOT NULL,
            percentual_do_total_municipal REAL NOT NULL,
            percentual_atencao_basica REAL NOT NULL,
            percentual_negra_derivado REAL NOT NULL,
            percentual_deficiencia REAL NOT NULL,
            percentual_lgbtqia_sobre_atencao_basica REAL NOT NULL
        );

        CREATE TABLE enderecos_por_distrito (
            id INTEGER PRIMARY KEY,
            distrito_sanitario_codigo TEXT NOT NULL
                REFERENCES distrito_populacao(distrito_sanitario_codigo),
            bairro TEXT NOT NULL,
            logradouro TEXT NOT NULL,
            numero TEXT NOT NULL,
            complemento TEXT,
            cep TEXT
        );

        CREATE TABLE cadastro_pec (
            id INTEGER PRIMARY KEY,
            identificador_simulado TEXT NOT NULL UNIQUE,
            endereco_id INTEGER NOT NULL REFERENCES enderecos_por_distrito(id),
            distrito_sanitario_codigo TEXT NOT NULL
                REFERENCES distrito_populacao(distrito_sanitario_codigo),
            digitado_por TEXT,
            data_digitacao TEXT,
            conferido_por TEXT,
            numero_folha TEXT,
            cns_profissional TEXT,
            cbo_profissional TEXT,
            cnes TEXT,
            ine TEXT,
            data_cadastro TEXT NOT NULL,
            cns_ou_cpf_cidadao TEXT,
            cidadao_responsavel_familiar INTEGER NOT NULL
                CHECK (cidadao_responsavel_familiar IN (0, 1)),
            cns_ou_cpf_responsavel TEXT,
            microarea TEXT,
            nome_completo TEXT NOT NULL,
            nome_social TEXT,
            data_nascimento TEXT NOT NULL,
            sexo TEXT NOT NULL CHECK (sexo IN ('F', 'M', 'I')),
            raca_cor TEXT NOT NULL
                CHECK (raca_cor IN ('Branca', 'Preta', 'Parda', 'Amarela', 'Indígena')),
            etnia TEXT,
            nis TEXT,
            nome_completo_mae TEXT,
            mae_desconhecida INTEGER NOT NULL CHECK (mae_desconhecida IN (0, 1)),
            nome_completo_pai TEXT,
            pai_desconhecido INTEGER NOT NULL CHECK (pai_desconhecido IN (0, 1)),
            nacionalidade TEXT NOT NULL,
            pais_nascimento TEXT,
            data_naturalizacao TEXT,
            portaria_naturalizacao TEXT,
            municipio_uf_nascimento TEXT,
            data_entrada_brasil TEXT,
            telefone_celular TEXT,
            email TEXT,
            ocupacao TEXT,
            situacao_mercado_trabalho TEXT,
            parentesco_responsavel_familiar TEXT,
            curso_mais_elevado TEXT,
            frequenta_escola_ou_creche TEXT,
            crianca_com_quem_fica TEXT,
            frequenta_cuidador_tradicional TEXT,
            participa_grupo_comunitario TEXT,
            possui_plano_saude_privado TEXT,
            povo_comunidade_tradicional TEXT,
            povo_comunidade_tradicional_qual TEXT,
            deseja_informar_orientacao_sexual TEXT,
            orientacao_sexual TEXT CHECK (
                orientacao_sexual IS NULL OR orientacao_sexual IN
                ('Heterossexual', 'Gay', 'Lésbica', 'Bissexual', 'Assexual',
                 'Pansexual', 'Outro')
            ),
            deseja_informar_identidade_genero TEXT,
            identidade_genero TEXT CHECK (
                identidade_genero IS NULL OR identidade_genero IN
                ('Homem cisgênero', 'Mulher cisgênero', 'Homem transgênero',
                 'Mulher transgênero', 'Travesti', 'Não-Binário', 'Outro')
            ),
            tem_deficiencia INTEGER NOT NULL CHECK (tem_deficiencia IN (0, 1)),
            tipo_deficiencia TEXT,
            mudou_territorio INTEGER NOT NULL CHECK (mudou_territorio IN (0, 1)),
            obito INTEGER NOT NULL CHECK (obito IN (0, 1)),
            data_obito TEXT,
            numero_declaracao_obito TEXT,
            recusou_cadastro INTEGER NOT NULL CHECK (recusou_cadastro IN (0, 1)),
            inseguranca_alimentar_alimentos_acabaram INTEGER NOT NULL
                CHECK (inseguranca_alimentar_alimentos_acabaram IN (0, 1)),
            inseguranca_alimentar_comida_limitada INTEGER NOT NULL
                CHECK (inseguranca_alimentar_comida_limitada IN (0, 1)),
            gestante INTEGER,
            maternidade_referencia TEXT,
            doenca_respiratoria INTEGER NOT NULL CHECK (doenca_respiratoria IN (0, 1)),
            doenca_respiratoria_tipo TEXT,
            fumante INTEGER NOT NULL CHECK (fumante IN (0, 1)),
            uso_alcool INTEGER NOT NULL CHECK (uso_alcool IN (0, 1)),
            hanseniase INTEGER NOT NULL CHECK (hanseniase IN (0, 1)),
            uso_outras_drogas INTEGER NOT NULL CHECK (uso_outras_drogas IN (0, 1)),
            tuberculose INTEGER NOT NULL CHECK (tuberculose IN (0, 1)),
            hipertensao INTEGER NOT NULL CHECK (hipertensao IN (0, 1)),
            cancer INTEGER NOT NULL CHECK (cancer IN (0, 1)),
            diabetes INTEGER NOT NULL CHECK (diabetes IN (0, 1)),
            internacao_ultimos_12_meses INTEGER NOT NULL
                CHECK (internacao_ultimos_12_meses IN (0, 1)),
            avc INTEGER NOT NULL CHECK (avc IN (0, 1)),
            infarto INTEGER NOT NULL CHECK (infarto IN (0, 1)),
            problema_saude_mental_diagnosticado INTEGER NOT NULL
                CHECK (problema_saude_mental_diagnosticado IN (0, 1)),
            doenca_cardiaca INTEGER NOT NULL CHECK (doenca_cardiaca IN (0, 1)),
            doenca_cardiaca_tipo TEXT,
            acamado INTEGER NOT NULL CHECK (acamado IN (0, 1)),
            domiciliado INTEGER NOT NULL CHECK (domiciliado IN (0, 1)),
            usa_plantas_medicinais INTEGER NOT NULL
                CHECK (usa_plantas_medicinais IN (0, 1)),
            problema_rins INTEGER NOT NULL CHECK (problema_rins IN (0, 1)),
            problema_rins_tipo TEXT,
            usa_praticas_integrativas INTEGER NOT NULL
                CHECK (usa_praticas_integrativas IN (0, 1))
        );

        """
    )


def gerar_cadastro(rng, sequencia, sexo, raca, pcd, lgbtqia):
    idade = rng.randint(10, 95) if lgbtqia else rng.randint(0, 95)

    if lgbtqia:
        orientacao, identidade = rng.choice(IDENTIDADES_LGBTQIA)
    else:
        orientacao = "Heterossexual"
        identidade = rng.choice(["Homem cisgênero", "Mulher cisgênero"])
    if idade < 10:
        orientacao = None
        identidade = None

    tipo_deficiencia = rng.choice(TIPOS_DEFICIENCIA) if pcd else None
    e_trans = identidade in (
        "Homem transgênero",
        "Mulher transgênero",
        "Travesti",
    )
    tem_deficiencia = int(pcd)
    sim_nao = lambda: rng.choice([0, 1])
    e_comunidade_tradicional = sim_nao()
    gestante = int(rng.random() < 0.03) if sexo == "F" and idade < 50 else None
    doenca_respiratoria = sim_nao()
    doenca_cardiaca = sim_nao()
    problema_rins = sim_nao()

    return {
        "digitado_por": f"Digitador Simulado {sequencia:06d}",
        "data_digitacao": "2026-10-21",
        "conferido_por": None,
        "numero_folha": None,
        "data_cadastro": "2026-10-21",
        "cns_ou_cpf_cidadao": None,
        "cidadao_responsavel_familiar": 1,
        "cns_ou_cpf_responsavel": None,
        "microarea": None,
        "nome_completo": f"Pessoa Simulada {sequencia:06d}",
        "nome_social": f"Nome Social Simulado {sequencia:06d}" if e_trans else None,
        "data_nascimento": gerar_data_nascimento(rng, idade),
        "sexo": sexo,
        "raca_cor": raca,
        "etnia": None,
        "nis": None,
        "nome_completo_mae": f"Mae Simulada {sequencia:06d}",
        "mae_desconhecida": 0,
        "nome_completo_pai": f"Pai Simulado {sequencia:06d}",
        "pai_desconhecido": 0,
        "nacionalidade": "Brasileira",
        "pais_nascimento": "Brasil",
        "data_naturalizacao": None,
        "portaria_naturalizacao": None,
        "municipio_uf_nascimento": "Recife/PE",
        "data_entrada_brasil": None,
        "telefone_celular": None,
        "email": None,
        "ocupacao": rng.choice(
            ["Estudante", "Comerciante", "Trabalhador(a) de servicos", "Outra"]
        ),
        "situacao_mercado_trabalho": rng.choice(
            ["Empregado(a)", "Autonomo(a)", "Desempregado(a)", "Nao trabalha"]
        ),
        "parentesco_responsavel_familiar": "Proprio(a)",
        "curso_mais_elevado": rng.choice(
            [
                "Ensino Fundamental Completo",
                "Ensino Fundamental EJA - series finais",
                "Ensino Medio, Medio 2 Ciclo",
                "Superior, Aperfeicoamento, Especializacao, Mestrado, Doutorado",
                "Nenhum",
            ]
        ),
        "frequenta_escola_ou_creche": (
            rng.choice(["Sim", "Nao"]) if idade < 25 else "Nao"
        ),
        "crianca_com_quem_fica": (
            rng.choice(["Adulto Responsavel", "Creche", "Outra Crianca", "Outro"])
            if idade < 10
            else None
        ),
        "frequenta_cuidador_tradicional": rng.choice(["Sim", "Nao"]),
        "participa_grupo_comunitario": rng.choice(["Sim", "Nao"]),
        "possui_plano_saude_privado": rng.choice(["Sim", "Nao"]),
        "povo_comunidade_tradicional": (
            "Sim" if e_comunidade_tradicional else "Nao"
        ),
        "povo_comunidade_tradicional_qual": (
            "Comunidade tradicional simulada"
            if e_comunidade_tradicional
            else None
        ),
        "deseja_informar_orientacao_sexual": None if idade < 10 else "Sim",
        "orientacao_sexual": orientacao,
        "deseja_informar_identidade_genero": None if idade < 10 else "Sim",
        "identidade_genero": identidade,
        "tem_deficiencia": tem_deficiencia,
        "tipo_deficiencia": tipo_deficiencia,
        "mudou_territorio": 0,
        "obito": 0,
        "data_obito": None,
        "numero_declaracao_obito": None,
        "recusou_cadastro": 0,
        "inseguranca_alimentar_alimentos_acabaram": sim_nao(),
        "inseguranca_alimentar_comida_limitada": sim_nao(),
        "gestante": gestante,
        "maternidade_referencia": "Maternidade Simulada" if gestante else None,
        "doenca_respiratoria": doenca_respiratoria,
        "doenca_respiratoria_tipo": (
            rng.choice(["Asma", "DPOC/Enfisema", "Outra", "Nao sabe"])
            if doenca_respiratoria
            else None
        ),
        "fumante": sim_nao(),
        "uso_alcool": sim_nao(),
        "hanseniase": 0,
        "uso_outras_drogas": sim_nao(),
        "tuberculose": 0,
        "hipertensao": int(rng.random() < 0.25) if idade >= 18 else 0,
        "cancer": sim_nao(),
        "diabetes": int(rng.random() < 0.12) if idade >= 18 else 0,
        "internacao_ultimos_12_meses": sim_nao(),
        "avc": 0,
        "infarto": 0,
        "problema_saude_mental_diagnosticado": sim_nao(),
        "doenca_cardiaca": doenca_cardiaca,
        "doenca_cardiaca_tipo": (
            rng.choice(["Insuficiencia Cardiaca", "Outra", "Nao sabe"])
            if doenca_cardiaca
            else None
        ),
        "acamado": 0,
        "domiciliado": 0,
        "usa_plantas_medicinais": sim_nao(),
        "problema_rins": problema_rins,
        "problema_rins_tipo": (
            rng.choice(["Insuficiencia Renal", "Outro", "Nao sabe"])
            if problema_rins
            else None
        ),
        "usa_praticas_integrativas": sim_nao(),
    }


def criar_banco(numero_registros=TOTAL_CADASTROS_ATENCAO_BASICA):
    if numero_registros < len(PESO_POPULACIONAL_DISTRITO):
        raise ValueError("Gere pelo menos um registro por distrito.")
    if sum(PESO_POPULACIONAL_DISTRITO.values()) != 1.0:
        raise ValueError("Os pesos populacionais distritais devem somar 100%.")
    if sum(PERCENTUAIS_RACA_COR.values()) != 1.0:
        raise ValueError("Os percentuais de raca/cor devem somar 100%.")

    bairros_por_distrito, fonte_bairros = carregar_bairros_por_distrito()
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    arquivo_temporario = ARQUIVO_DB.with_suffix(".tmp")
    if arquivo_temporario.exists():
        arquivo_temporario.unlink()
    conexao = sqlite3.connect(arquivo_temporario)
    conexao.execute("PRAGMA journal_mode = OFF")
    conexao.execute("PRAGMA synchronous = OFF")
    conexao.execute("PRAGMA temp_store = MEMORY")
    conexao.execute("PRAGMA foreign_keys = ON")

    try:
        with conexao:
            cursor = conexao.cursor()
            criar_esquema(cursor)

            populacao_distrito = arredondar_por_pesos(
                POPULACAO_RECIFE, PESO_POPULACIONAL_DISTRITO
            )
            atendidos_total = arredondar_percentual(
                POPULACAO_RECIFE, PERCENTUAL_ATENCAO_BASICA
            )
            atendidos_distrito = arredondar_por_pesos(
                atendidos_total, PESO_POPULACIONAL_DISTRITO
            )
            sexo_populacao_distrito = distribuir_categorias_por_distrito(
                populacao_distrito, SEXO_POPULACAO_CENSO_2022
            )
            sexo_atencao_basica_distrito = distribuir_categorias_por_distrito(
                atendidos_distrito,
                SEXO_POPULACAO_CENSO_2022,
            )
            distribuicao_raca_populacao = distribuir_categorias_por_distrito(
                populacao_distrito, PERCENTUAIS_RACA_COR
            )
            deficiencia_total = arredondar_percentual(
                POPULACAO_RECIFE, PERCENTUAL_DEFICIENCIA
            )
            deficiencia_distrito = arredondar_por_pesos(
                deficiencia_total, PESO_POPULACIONAL_DISTRITO
            )
            deficiencia_atencao_basica_total = arredondar_percentual(
                atendidos_total, PERCENTUAL_DEFICIENCIA
            )
            deficiencia_atencao_basica_distrito = arredondar_por_pesos(
                deficiencia_atencao_basica_total,
                PESO_POPULACIONAL_DISTRITO,
            )
            lgbtqia_total = arredondar_percentual(
                atendidos_total, PERCENTUAL_LGBTQIA_ATENCAO_BASICA
            )
            lgbtqia_distrito = arredondar_por_pesos(
                lgbtqia_total, PESO_POPULACIONAL_DISTRITO
            )
            registros_distrito = arredondar_por_pesos(
                numero_registros, PESO_POPULACIONAL_DISTRITO
            )
            distribuicao_sexo_amostra = distribuir_categorias_por_distrito(
                registros_distrito, SEXO_POPULACAO_CENSO_2022
            )
            distribuicao_raca_amostra = distribuir_categorias_por_distrito(
                registros_distrito, PERCENTUAIS_RACA_COR
            )
            distribuicao_pcd_amostra = distribuir_categorias_por_distrito(
                registros_distrito,
                {
                    False: 1 - PERCENTUAL_DEFICIENCIA,
                    True: PERCENTUAL_DEFICIENCIA,
                },
            )
            distribuicao_lgbtqia_amostra = arredondar_por_pesos(
                arredondar_percentual(
                    numero_registros,
                    PERCENTUAL_LGBTQIA_ATENCAO_BASICA,
                ),
                PESO_POPULACIONAL_DISTRITO,
            )

            for codigo in PESO_POPULACIONAL_DISTRITO:
                total = populacao_distrito[codigo]
                raca_counts = distribuicao_raca_populacao[codigo]
                populacao_negra = raca_counts["Preta"] + raca_counts["Parda"]
                cursor.execute(
                    """
                    INSERT INTO distrito_populacao VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        codigo,
                        f"Distrito {['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII'][int(codigo) - 1]}",
                        PESO_POPULACIONAL_DISTRITO[codigo],
                        total,
                        atendidos_distrito[codigo],
                        sexo_populacao_distrito[codigo]["F"],
                        sexo_populacao_distrito[codigo]["M"],
                        sexo_populacao_distrito[codigo]["I"],
                        sexo_atencao_basica_distrito[codigo]["F"],
                        sexo_atencao_basica_distrito[codigo]["M"],
                        sexo_atencao_basica_distrito[codigo]["I"],
                        raca_counts["Branca"],
                        raca_counts["Preta"],
                        raca_counts["Parda"],
                        raca_counts["Amarela"],
                        raca_counts["Indígena"],
                        populacao_negra,
                        deficiencia_distrito[codigo],
                        deficiencia_atencao_basica_distrito[codigo],
                        lgbtqia_distrito[codigo],
                        total / POPULACAO_RECIFE,
                        PERCENTUAL_ATENCAO_BASICA,
                        populacao_negra / total,
                        PERCENTUAL_DEFICIENCIA,
                        PERCENTUAL_LGBTQIA_ATENCAO_BASICA,
                    ),
                )

            cursor.executemany(
                "INSERT INTO metadados_simulacao VALUES (?, ?)",
                [
                    ("tipo_dado", "SINTETICO - nao representa pessoas reais"),
                    ("formulario_referencia", "Ficha de Cadastro Individual PEC/e-SUS APS v5.31"),
                    ("populacao_municipal", str(POPULACAO_RECIFE)),
                    ("percentual_atencao_basica", str(PERCENTUAL_ATENCAO_BASICA)),
                    ("cadastros_simulados", str(numero_registros)),
                    ("cadastros_padrao_80_porcento", str(TOTAL_CADASTROS_ATENCAO_BASICA)),
                    ("percentual_deficiencia_sobre_total", str(PERCENTUAL_DEFICIENCIA)),
                    ("percentual_deficiencia_na_atencao_basica", str(PERCENTUAL_DEFICIENCIA)),
                    ("percentual_lgbtqia_sobre_atencao_basica", str(PERCENTUAL_LGBTQIA_ATENCAO_BASICA)),
                    ("cadastros_com_deficiencia", str(arredondar_percentual(numero_registros, PERCENTUAL_DEFICIENCIA))),
                    ("cadastros_lgbtqia", str(arredondar_percentual(numero_registros, PERCENTUAL_LGBTQIA_ATENCAO_BASICA))),
                    ("percentual_negra_derivado", "0.608 = 0.485 parda + 0.123 preta"),
                    ("raca_cor_amarela", "0.002 - metade do restante de 0.004"),
                    ("raca_cor_indigena", "0.002 - metade do restante de 0.004"),
                    ("sexo_feminino_censo_2022", str(SEXO_POPULACAO_CENSO_2022["F"])),
                    ("sexo_masculino_censo_2022", str(SEXO_POPULACAO_CENSO_2022["M"])),
                    ("fonte_sexo", "IBGE SIDRA tabela 9514, Recife, Censo 2022"),
                    ("url_fonte_sexo", "https://apisidra.ibge.gov.br/values/t/9514/n6/2611606/v/93/p/2022/c2/all"),
                    ("sexo_ignorado_pec", "0; o Censo informa Homens e Mulheres, sem categoria I"),
                    ("pesos_distritais", json.dumps(PESO_POPULACIONAL_DISTRITO, ensure_ascii=False)),
                    ("pesos_distritais_status", "ILUSTRATIVOS - precisam ser substituidos por populacao oficial por distrito"),
                    ("fonte_mapa_bairros", fonte_bairros),
                    ("endereco", "Bairros reais; logradouros e numeros sinteticos; CEP e contatos vazios"),
                    ("identificadores", "CNS/CPF/NIS/CNS profissional/CBO/CNES/INE omitidos; nao gerar identificadores reais"),
                    ("campos_de_saude", "Valores sinteticos ilustrativos; nao sao prevalencias nem diagnósticos reais"),
                    ("base_amostral_formularios", "80% da populacao municipal quando gerado no tamanho padrao"),
                    ("semente_aleatoria", str(SEED)),
                ],
            )

            sequencia = 0
            for codigo, quantidade in registros_distrito.items():
                categorias_raca = []
                categorias_sexo = []
                for raca in RACAS:
                    categorias_raca.extend(
                        [raca] * distribuicao_raca_amostra[codigo][raca]
                    )
                for sexo in SEXO_POPULACAO_CENSO_2022:
                    categorias_sexo.extend(
                        [sexo] * distribuicao_sexo_amostra[codigo][sexo]
                    )
                if (
                    len(categorias_raca) != quantidade
                    or len(categorias_sexo) != quantidade
                ):
                    raise RuntimeError(
                        f"Distribuicao de sexo ou raca/cor invalida "
                        f"no distrito {codigo}."
                    )
                rng.shuffle(categorias_raca)
                rng.shuffle(categorias_sexo)

                quantidade_pcd = distribuicao_pcd_amostra[codigo][True]
                quantidade_lgbtqia = distribuicao_lgbtqia_amostra[codigo]
                indices_pcd = set(rng.sample(range(quantidade), quantidade_pcd))
                indices_lgbtqia = set(
                    rng.sample(range(quantidade), quantidade_lgbtqia)
                )
                bairros = bairros_por_distrito[codigo]

                lote_enderecos = []
                lote_cadastros = []
                for indice in range(quantidade):
                    sequencia += 1
                    bairro = rng.choice(bairros)
                    endereco_id = sequencia
                    lote_enderecos.append(
                        (
                            endereco_id,
                            codigo,
                            bairro,
                            f"LOGRADOURO SIMULADO {sequencia:07d}",
                            f"{rng.randint(1, 9999):04d}",
                        )
                    )
                    registro = gerar_cadastro(
                        rng,
                        sequencia,
                        categorias_sexo[indice],
                        categorias_raca[indice],
                        indice in indices_pcd,
                        indice in indices_lgbtqia,
                    )
                    colunas = [
                        "identificador_simulado",
                        "endereco_id",
                        "distrito_sanitario_codigo",
                        "cns_profissional",
                        "cbo_profissional",
                        "cnes",
                        "ine",
                    ] + list(registro.keys())
                    valores = [
                        f"SIM-{sequencia:06d}",
                        endereco_id,
                        codigo,
                        None,
                        None,
                        None,
                        None,
                    ] + list(registro.values())
                    lote_cadastros.append(valores)
                    if len(lote_cadastros) >= 2000:
                        cursor.executemany(
                            """
                            INSERT INTO enderecos_por_distrito (
                                id, distrito_sanitario_codigo, bairro, logradouro,
                                numero, complemento, cep
                            ) VALUES (?, ?, ?, ?, ?, NULL, NULL)
                            """,
                            lote_enderecos,
                        )
                        cursor.executemany(
                            f"INSERT INTO cadastro_pec ({', '.join(colunas)}) "
                            f"VALUES ({', '.join('?' for _ in valores)})",
                            lote_cadastros,
                        )
                        lote_enderecos.clear()
                        lote_cadastros.clear()

                if lote_cadastros:
                    cursor.executemany(
                        """
                        INSERT INTO enderecos_por_distrito (
                            id, distrito_sanitario_codigo, bairro, logradouro,
                            numero, complemento, cep
                        ) VALUES (?, ?, ?, ?, ?, NULL, NULL)
                        """,
                        lote_enderecos,
                    )
                    cursor.executemany(
                        f"INSERT INTO cadastro_pec ({', '.join(colunas)}) "
                        f"VALUES ({', '.join('?' for _ in valores)})",
                        lote_cadastros,
                    )

        with conexao:
            total_formularios = conexao.execute(
                "SELECT COUNT(*) FROM cadastro_pec"
            ).fetchone()[0]
            if total_formularios != numero_registros:
                raise RuntimeError(
                    f"Esperava {numero_registros} formularios, "
                    f"mas foram gravados {total_formularios}."
                )
            integridade = conexao.execute("PRAGMA integrity_check").fetchone()[0]
            if integridade != "ok":
                raise RuntimeError(
                    f"Falha na verificacao de integridade do SQLite: {integridade}"
                )
    except Exception:
        conexao.close()
        if arquivo_temporario.exists():
            arquivo_temporario.unlink()
        raise
    else:
        conexao.close()

    arquivo_temporario.replace(ARQUIVO_DB)
    print(f"Banco SQLite gerado: {ARQUIVO_DB}")
    print(f"Formularios sinteticos: {numero_registros:,}")
    print(f"Populacao municipal de referencia: {POPULACAO_RECIFE:,}")
    print(f"Populacao estimada em atencao basica (80%): {atendidos_total:,}")
    print("Pesos de populacao por distrito: ilustrativos, nao oficiais.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registros",
        type=int,
        default=TOTAL_CADASTROS_ATENCAO_BASICA,
        help=(
            "quantidade de formularios sinteticos; por padrao, 80%% da "
            f"populacao do Recife ({TOTAL_CADASTROS_ATENCAO_BASICA:,})"
        ),
    )
    argumentos = parser.parse_args()
    criar_banco(argumentos.registros)
