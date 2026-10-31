import os
import re
import unicodedata
from decimal import Decimal

import ollama
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

load_dotenv()

NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL")
MODELO_SQL = "llama3.2"
MODELO_RESPOSTA = "llama3.2"

ESQUEMA_BANCO = """
Tabelas disponíveis no banco (PostgreSQL):

unidades_saude(
    cnes TEXT, nome_fantasia TEXT, nome_empresarial TEXT, bairro TEXT,
    distrito_sanitario_codigo TEXT, distrito_sanitario_nome TEXT,
    endereco TEXT, cep TEXT, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION,
    tipo_estabelecimento TEXT
)

IMPORTANTE sobre distrito_sanitario_codigo: é um texto numérico com zero à
esquerda (dois dígitos). Use exatamente esta tabela de conversão, com cuidado
especial para não confundir VII com VIII (são códigos consecutivos e
parecidos):
'01' = Distrito I
'02' = Distrito II
'03' = Distrito III
'04' = Distrito IV
'05' = Distrito V
'06' = Distrito VI
'07' = Distrito VII
'08' = Distrito VIII (NÃO é '07' — VIII tem um "I" extra no final em relação a VII)
Quando o usuário mencionar um distrito em número romano (ex: "Distrito I",
"Distrito IV"), converta para esse código numérico de dois dígitos e filtre
por distrito_sanitario_codigo. NÃO filtre por distrito_sanitario_nome usando o
número romano isolado — "I" aparece como substring dentro de "II", "III",
"VII" e "VIII", o que gera resultado errado.
Algumas unidades têm distrito_sanitario_codigo em branco (NULL) — são
hospitais, laboratórios e outros tipos que não pertencem a um Distrito
Sanitário; isso é esperado, não é erro de dado.

IMPORTANTE: a tabela unidades_saude já contém APENAS unidades de Recife —
não existe coluna de cidade/município, e o campo cep é só o CEP numérico
(não contém o nome "Recife" escrito nele). Se a pergunta mencionar "Recife",
NÃO filtre por cep, endereco ou qualquer texto — ignore a palavra "Recife" e
consulte a tabela inteira, sem filtro de cidade.

Para contar quantos distritos sanitários distintos existem, use
COUNT(DISTINCT distrito_sanitario_codigo) e sempre exclua os valores NULL com
WHERE distrito_sanitario_codigo IS NOT NULL. Preste atenção ao digitar o nome
da coluna exatamente como está definido aqui: distrito_sanitario_codigo (não
"distro_sanitario_codigo" nem outra variação).

Para perguntas de ranking/comparação entre distritos (ex: "qual distrito tem
mais unidades", "qual distrito tem menos equipes"), sempre adicione
WHERE distrito_sanitario_codigo IS NOT NULL antes do GROUP BY. Sem esse
filtro, as unidades sem distrito (hospitais, laboratórios) formam um grupo
próprio que pode aparecer como "vencedor" do ranking, o que é errado — elas
não pertencem a nenhum distrito.

equipes_saude(
    codigo_equipe TEXT, nome_equipe TEXT, tipo_equipe TEXT,
    cnes_unidade TEXT, data_ativacao TEXT, data_desativacao TEXT
)

Sobre o status da equipe: uma equipe que ainda está ativa (realmente
atendendo hoje) tem data_desativacao NULL (em branco). Uma equipe com
data_desativacao preenchida já foi desativada e não atende mais. Quando a
pergunta mencionar "ativas", "que atendem", "em funcionamento" ou "em
operação", filtre com WHERE data_desativacao IS NULL. Quando mencionar
"desativadas" ou "que não atendem mais", filtre com
WHERE data_desativacao IS NOT NULL. Quando a pergunta pedir apenas o "total"
sem menção a status, não filtre por data_desativacao — conte todas.

censo_raca_cor(
    raca_cor TEXT, populacao BIGINT, ano INTEGER
)

Os únicos valores que existem na coluna raca_cor são exatamente estes 5,
escritos assim: 'Branca', 'Preta', 'Parda', 'Amarela', 'Indígena'. Não existe
nenhum outro valor nessa coluna — nunca invente uma categoria diferente
dessas.

IMPORTANTE sobre "população negra": não existe uma categoria 'Negra' na
coluna raca_cor. Pela definição usada pelo IBGE e pelas políticas de equidade
racial, "população negra" = soma de 'Preta' + 'Parda'. Quando a pergunta
mencionar "negra", "negros" ou "pessoas negras", SOME as duas categorias
('Preta' e 'Parda') — nunca retorne apenas 'Preta' isolada, isso sub-representa
gravemente o número real.

censo_deficiencia(
    tipo_dificuldade TEXT, populacao BIGINT, ano INTEGER, e_total BOOLEAN
)

Os únicos valores que existem na coluna tipo_dificuldade são: 'Total' (quando
e_total = true) e, quando e_total = false, um destes 5 textos exatos:
'Dificuldade permanente para enxergar, mesmo usando óculos ou lentes de
contato', 'Dificuldade permanente para ouvir, mesmo usando aparelhos
auditivos', 'Dificuldade permanente para andar ou subir degraus, mesmo usando
prótese ou outro aparelho de auxílio', 'Dificuldade permanente para pegar
pequenos objetos, como botão ou lápis, ou abrir e fechar tampas de garrafas,
mesmo usando aparelho de auxílio', 'Dificuldade permanente para se comunicar,
realizar cuidados pessoais, trabalhar ou estudar por causa de alguma
limitação nas funções mentais'. Para perguntas sobre o TOTAL de pessoas com
deficiência (sem especificar um tipo), use WHERE e_total = true e NÃO filtre
por tipo_dificuldade.

Regra importante: em censo_deficiencia, a linha com e_total = true é o total
oficial de pessoas com deficiência; as linhas com e_total = false são tipos de
dificuldade específicos, que NÃO devem ser somados entre si (uma pessoa pode
ter mais de um tipo de dificuldade). Mesmo que a pergunta peça explicitamente
para "somar os tipos" ou "somar todas as dificuldades", IGNORE esse pedido e
retorne o valor de e_total = true, pois somar os tipos gera um número inflado
e estatisticamente errado — o total correto já está pronto na linha
e_total = true.

IMPORTANTE: as tabelas censo_deficiencia e censo_raca_cor NÃO têm nenhuma
coluna de território (não têm cidade, bairro, distrito). Elas já representam
o Recife inteiro. NUNCA adicione um filtro tipo "WHERE ... = 'Recife'" nessas
duas tabelas — essa coluna não existe e a consulta vai falhar. Se a pergunta
mencionar "Recife", ignore essa palavra ao montar o SQL para essas duas
tabelas, pois já é implícito.

IMPORTANTE sobre a coluna ano: em censo_raca_cor e censo_deficiencia, o único
valor existente é 2022 (dado do Censo Demográfico 2022). Não assuma outro ano
(como o ano atual) — se a pergunta não especificar um ano, não filtre por ano,
ou use ano = 2022.

Exemplos de pergunta e o SQL correto correspondente:

Pergunta: Quantas unidades de saúde tem no Distrito Sanitário I?
SQL: SELECT COUNT(*) FROM unidades_saude WHERE distrito_sanitario_codigo = '01';

Pergunta: Quantas unidades de saúde tem em Recife?
SQL: SELECT COUNT(*) FROM unidades_saude;

Pergunta: Quantos distritos sanitários existem?
SQL: SELECT COUNT(DISTINCT distrito_sanitario_codigo) FROM unidades_saude WHERE distrito_sanitario_codigo IS NOT NULL;

Pergunta: Quantas unidades de saúde tem no Distrito VIII?
SQL: SELECT COUNT(*) FROM unidades_saude WHERE distrito_sanitario_codigo = '08';

Pergunta: Qual distrito tem mais unidades de saúde?
SQL: SELECT distrito_sanitario_nome FROM unidades_saude WHERE distrito_sanitario_codigo IS NOT NULL GROUP BY distrito_sanitario_nome ORDER BY COUNT(*) DESC LIMIT 1;

Pergunta: Some todos os tipos de dificuldade e me diga o total de pessoas com deficiência
SQL: SELECT populacao FROM censo_deficiencia WHERE e_total = true;

Pergunta: Quantas pessoas com deficiência tem no Recife?
SQL: SELECT populacao FROM censo_deficiencia WHERE e_total = true;

Pergunta: Qual a população parda do Recife?
SQL: SELECT populacao FROM censo_raca_cor WHERE raca_cor = 'Parda';

Pergunta: Quantas pessoas negras tem em Recife?
SQL: SELECT SUM(populacao) FROM censo_raca_cor WHERE raca_cor IN ('Preta', 'Parda');

Pergunta: Quantas equipes de saúde da família existem no total?
SQL: SELECT COUNT(*) FROM equipes_saude;

Pergunta: Quantas equipes estão ativas, ou seja, sem data de desativação?
SQL: SELECT COUNT(*) FROM equipes_saude WHERE data_desativacao IS NULL;

Pergunta: Quantas equipes já foram desativadas?
SQL: SELECT COUNT(*) FROM equipes_saude WHERE data_desativacao IS NOT NULL;

mock_pec_atendimentos(
    id_atendimento INTEGER, codigo_equipe TEXT, cnes_unidade TEXT,
    distrito_sanitario_codigo TEXT, data_atendimento DATE, tipo_atendimento TEXT,
    profissional_tipo TEXT, idade INTEGER, raca_cor TEXT, deficiencia_tipo TEXT,
    deseja_informar_orientacao_sexual TEXT, orientacao_sexual TEXT,
    deseja_informar_identidade_genero TEXT, identidade_genero TEXT, nome_social TEXT
)

IMPORTANTE: esta tabela contém dados FICTÍCIOS/SIMULADOS (não são pacientes
reais), gerados para testar o pipeline enquanto o acesso ao PEC/e-SUS real não
é liberado pela Secretaria. Um atendimento por linha, ligado a uma equipe de
saúde real.

Sobre distrito_sanitario_codigo nesta tabela: usa o MESMO código de dois
dígitos ('01' a '08') que a tabela unidades_saude — mesma regra de conversão
romano→código já explicada acima.

Sobre profissional_tipo: valores possíveis são 'ACS', 'Enfermeiro', 'Médico'.
Quando a pergunta mencionar "agentes comunitários" ou "ACS", filtre com
WHERE profissional_tipo = 'ACS'.

Sobre raca_cor nesta tabela: mesmas 5 categorias de censo_raca_cor ('Branca',
'Preta', 'Parda', 'Amarela', 'Indígena'), OU NULL quando o campo não foi
preenchido no atendimento (simulando o sub-registro real). COUNT(raca_cor) em
SQL já ignora os NULL automaticamente, não precisa de WHERE extra.

Sobre deficiencia_tipo nesta tabela: um dos 5 tipos de dificuldade (mesmos
textos de censo_deficiencia, exceto 'Total'), OU 'Nenhuma' (a pessoa foi
perguntada e não tem deficiência — isso CONTA como campo preenchido), OU NULL
quando o campo não foi perguntado/preenchido. Para completude, use
COUNT(deficiencia_tipo), que conta 'Nenhuma' como preenchido corretamente e
ignora só os NULL.

Sobre orientação sexual e identidade de gênero — ESTRUTURA EM DUAS ETAPAS,
igual ao PEC real:
- deseja_informar_orientacao_sexual: 'Sim', 'Não', ou NULL.
  NULL = o profissional NUNCA perguntou (campo em branco — o problema mais
  grave, ligado à falta de capacitação do ACS).
  'Não' = o profissional perguntou, mas a pessoa não quis informar.
  'Sim' = a pessoa informou, e a categoria está na coluna orientacao_sexual.
- orientacao_sexual: só é preenchida quando deseja_informar_orientacao_sexual
  = 'Sim'. Valores possíveis: 'Heterossexual', 'Gay', 'Lésbica', 'Bissexual',
  'Assexual', 'Pansexual', 'Outro'.
- A mesma lógica de três estados se repete para
  deseja_informar_identidade_genero / identidade_genero. Valores possíveis de
  identidade_genero: 'Mulher cisgênero', 'Homem cisgênero', 'Mulher trans',
  'Homem trans', 'Não-binário', 'Outro'.
- nome_social: preenchido só quando identidade_genero é 'Mulher trans' ou
  'Homem trans'.

Regra de negócio definida pela Secretaria: atendimentos de pessoas com
idade < 10 NUNCA têm orientação sexual ou identidade de gênero preenchidas —
isso é esperado, não é erro nem falta de preenchimento pelo ACS.

Definição de "completude" (proporção de campo preenchido, para ranking e KPI
— sempre multiplique por 100 e use ROUND(..., 1) se a pergunta pedir
percentual):
- Completude de raça/cor: COUNT(raca_cor)::numeric / COUNT(*)
- Completude de deficiência: COUNT(deficiencia_tipo)::numeric / COUNT(*)
- Completude de orientação sexual (o profissional pelo menos perguntou):
  COUNT(deseja_informar_orientacao_sexual)::numeric / COUNT(*)
- Completude de identidade de gênero: mesma lógica com
  deseja_informar_identidade_genero

Definição de "população LGBTQIAPN+" nesta tabela: pessoas cuja
orientacao_sexual NÃO é 'Heterossexual' (e não é nula) OU cujo
identidade_genero está em ('Mulher trans', 'Homem trans', 'Não-binário'). Use
OR entre as duas condições, nunca considere só uma isoladamente.

mock_populacao_negra_distrito(
    distrito_sanitario_codigo TEXT, populacao_negra_pct_esperado NUMERIC
)

IMPORTANTE: esta tabela também é FICTÍCIA/SIMULADA — é um percentual
ilustrativo de referência, não o dado real do Censo por distrito (que não
existe nessa granularidade). populacao_negra_pct_esperado é um número entre 0
e 1 (ex.: 0.42 significa 42%).

Para comparar o percentual observado de população negra num distrito (a
partir de mock_pec_atendimentos) com o esperado (mock_populacao_negra_distrito),
faça um JOIN pelas duas tabelas usando distrito_sanitario_codigo.

Pergunta: Quantos atendimentos fictícios existem no total na base de simulação?
SQL: SELECT COUNT(*) FROM mock_pec_atendimentos;

Pergunta: Qual a taxa de completude do campo raça/cor?
SQL: SELECT ROUND(COUNT(raca_cor)::numeric / COUNT(*) * 100, 1) FROM mock_pec_atendimentos;

Pergunta: Quantos atendimentos têm o campo de orientação sexual em branco, ou seja, nunca perguntado?
SQL: SELECT COUNT(*) FROM mock_pec_atendimentos WHERE deseja_informar_orientacao_sexual IS NULL;

Pergunta: Quais são as 5 equipes com pior completude de orientação sexual, considerando só atendimentos feitos por ACS?
SQL: SELECT codigo_equipe, ROUND(COUNT(deseja_informar_orientacao_sexual)::numeric / COUNT(*) * 100, 1) AS completude FROM mock_pec_atendimentos WHERE profissional_tipo = 'ACS' GROUP BY codigo_equipe ORDER BY completude ASC LIMIT 5;

Pergunta: Quantas pessoas informaram identidade de gênero trans?
SQL: SELECT COUNT(*) FROM mock_pec_atendimentos WHERE identidade_genero IN ('Mulher trans', 'Homem trans');

Pergunta: Quantas pessoas se identificam como LGBTQIAPN+?
SQL: SELECT COUNT(*) FROM mock_pec_atendimentos WHERE (orientacao_sexual IS NOT NULL AND orientacao_sexual != 'Heterossexual') OR identidade_genero IN ('Mulher trans', 'Homem trans', 'Não-binário');

Pergunta: Quantas pessoas com deficiência foram atendidas?
SQL: SELECT COUNT(*) FROM mock_pec_atendimentos WHERE deficiencia_tipo IS NOT NULL AND deficiencia_tipo != 'Nenhuma';

Pergunta: Qual equipe tem a pior completude do campo raça/cor?
SQL: SELECT codigo_equipe, ROUND(COUNT(raca_cor)::numeric / COUNT(*) * 100, 1) AS completude FROM mock_pec_atendimentos GROUP BY codigo_equipe ORDER BY completude ASC LIMIT 1;

Pergunta: Em qual distrito sanitário há mais pessoas LGBTQIAPN+ registradas?
SQL: SELECT distrito_sanitario_codigo, COUNT(*) AS total FROM mock_pec_atendimentos WHERE (orientacao_sexual IS NOT NULL AND orientacao_sexual != 'Heterossexual') OR identidade_genero IN ('Mulher trans', 'Homem trans', 'Não-binário') GROUP BY distrito_sanitario_codigo ORDER BY total DESC LIMIT 1;

Pergunta: Quantos atendimentos foram feitos por agentes comunitários de saúde?
SQL: SELECT COUNT(*) FROM mock_pec_atendimentos WHERE profissional_tipo = 'ACS';

Pergunta: Qual a idade média dos pacientes atendidos?
SQL: SELECT ROUND(AVG(idade), 1) FROM mock_pec_atendimentos;

Pergunta: Qual distrito tem o maior gap entre população negra esperada e observada?
SQL: SELECT a.distrito_sanitario_codigo, p.populacao_negra_pct_esperado, ROUND(COUNT(*) FILTER (WHERE a.raca_cor IN ('Preta','Parda'))::numeric / COUNT(a.raca_cor), 3) AS pct_observado FROM mock_pec_atendimentos a JOIN mock_populacao_negra_distrito p ON p.distrito_sanitario_codigo = a.distrito_sanitario_codigo GROUP BY a.distrito_sanitario_codigo, p.populacao_negra_pct_esperado ORDER BY (p.populacao_negra_pct_esperado - (COUNT(*) FILTER (WHERE a.raca_cor IN ('Preta','Parda'))::numeric / COUNT(a.raca_cor))) DESC LIMIT 1;

Pergunta: Quantos atendimentos de crianças menores de 10 anos existem?
SQL: SELECT COUNT(*) FROM mock_pec_atendimentos WHERE idade < 10;
"""


def gerar_sql_contagem_simples(pergunta):
    normalizada = unicodedata.normalize("NFKD", pergunta.casefold())
    normalizada = "".join(
        caractere for caractere in normalizada
        if not unicodedata.combining(caractere)
    )
    pede_contagem = (
        re.search(r"\bquantas?\b", normalizada)
        or re.search(r"\bnumero de\b", normalizada)
        or re.search(r"\btotal\b", normalizada)
        or re.search(r"\bao todo\b", normalizada)
    )
    pede_total_simples = not re.search(
        r"\b(por|cada|ranking|distrito|bairro|tipo|ativa|desativada)\b",
        normalizada,
    )
    if (
        pede_contagem
        and pede_total_simples
        and re.search(r"\bunidades? de saude\b", normalizada)
    ):
        return "SELECT COUNT(*) FROM unidades_saude;"
    return None


def gerar_sql(pergunta, erro_anterior=None):
    sql_deterministico = gerar_sql_contagem_simples(pergunta)
    if sql_deterministico:
        return sql_deterministico

    correcao = ""
    if erro_anterior:
        sql_anterior, mensagem_erro = erro_anterior
        correcao = f"""

A tentativa anterior não foi aceita pelo PostgreSQL.
SQL anterior: {sql_anterior}
Erro retornado: {mensagem_erro}
Gere uma consulta corrigida, usando somente tabelas e colunas declaradas
no esquema acima. Não invente nomes de colunas.
"""

    prompt = f"""{ESQUEMA_BANCO}

Escreva APENAS um comando SQL (PostgreSQL) que responda à pergunta abaixo.
Use somente tabelas e colunas declaradas no esquema. Não invente nomes de
colunas. Não escreva explicações, não use blocos de markdown, escreva somente
o SQL puro.

Pergunta: {pergunta}
{correcao}
SQL:"""

    resposta = ollama.chat(
        model=MODELO_SQL,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0},
    )
    sql_bruto = resposta["message"]["content"]
    return re.sub(r"```sql|```", "", sql_bruto).strip()


def rodar_sql(sql):
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError(
            "Por segurança, só executo comandos SELECT. "
            f"O modelo gerou: {sql}"
        )

    engine = create_engine(NEON_DATABASE_URL)
    with engine.connect() as conexao:
        conexao.exec_driver_sql("SET TRANSACTION READ ONLY")
        resultado = conexao.execute(text(sql))
        linhas = resultado.fetchall()
        colunas = resultado.keys()
    return colunas, linhas


def formatar_numero_br(valor):
    valor_float = float(valor)
    parte_inteira = int(valor_float)
    inteira_formatada = f"{parte_inteira:,}".replace(",", ".")
    if valor_float == parte_inteira:
        return inteira_formatada
    texto_decimal = f"{abs(valor_float - parte_inteira):.1f}".split(".")[1]
    return f"{inteira_formatada},{texto_decimal}"


def gerar_resposta_em_texto(pergunta, colunas, linhas):
    dados_formatados = "\n".join(
        ", ".join(f"{col}: {valor}" for col, valor in zip(colunas, linha))
        for linha in linhas
    )
    print(f"[Dados retornados pelo Neon]: {dados_formatados}\n")

    if not linhas:
        return "Não encontrei nenhum resultado para essa pergunta no banco de dados."

    if len(linhas) == 1 and len(colunas) == 1:
        valor = linhas[0][0]
        if isinstance(valor, (int, float, Decimal)):
            valor = formatar_numero_br(valor)
        return f"A resposta é {valor}."

    prompt = f"""Reescreva os dados abaixo como uma frase em português, de forma
direta e objetiva. Não adicione opiniões, ressalvas ou comentários — apenas
transcreva os números em uma frase.

Pergunta: {pergunta}
Dados: {dados_formatados}

Frase:"""

    resposta = ollama.chat(
        model=MODELO_RESPOSTA,
        messages=[{"role": "user", "content": prompt}],
    )
    return resposta["message"]["content"]


def responder_pergunta(pergunta):
    erro_anterior = None
    for tentativa in range(2):
        sql = gerar_sql(pergunta, erro_anterior)
        print(f"[SQL gerado pelo modelo]: {sql}\n")
        try:
            colunas, linhas = rodar_sql(sql)
            break
        except ProgrammingError as erro:
            if tentativa == 1:
                raise ValueError(
                    "O assistente não conseguiu gerar uma consulta válida "
                    "para essa pergunta. Tente reformulá-la."
                ) from erro
            erro_anterior = (sql, str(erro.orig))

    resposta = gerar_resposta_em_texto(pergunta, colunas, linhas)

    if "mock_" in sql.lower():
        resposta += " (dado simulado, para fins de demonstração — não representa a realidade de Recife)"

    return resposta


if __name__ == "__main__":
    pergunta = input("Pergunte sobre os dados: ")
    print("\n" + responder_pergunta(pergunta))
