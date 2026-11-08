# ETL — Políticas de Equidade em Saúde (Recife)

## Autores

- José Bruno
- Felipe Saraiva
- Rodrigo Aguiar

CESAR School

## Contexto do desafio

A Secretaria de Atenção Básica do Recife enfrenta dificuldade para transformar os dados do **PEC/e-SUS APS** (sistema de prontuário da Atenção Primária à Saúde) em indicadores estratégicos para três políticas municipais de equidade:

- Saúde Integral da População LGBTQIAPN+
- Atenção Integral à Saúde da Pessoa com Deficiência
- Saúde Integral da População Negra

Os dados existem no PEC/e-SUS, mas estão dispersos e exigem hoje um processo manual de extração e análise, feito por unidade de saúde — não por Equipe de Saúde da Família, que é o nível em que a gestão precisaria agir para priorizar capacitação. Raça/cor e deficiência já são campos obrigatórios no sistema, mas sem garantia de completude; orientação sexual e identidade de gênero dependem de um filtro de duas etapas ("deseja informar?" → categoria), o que resulta em um alto volume de registros "não informado" — e os dados de LGBTQIAPN+ ainda dependem de planilhas extraídas manualmente, sem relatório sistematizado no próprio PEC. Esse sub-registro é atribuído, em boa parte, aos Agentes Comunitários de Saúde (ACS), que muitas vezes não chegam a perguntar esses campos.

Resolver isso destravaria decisões concretas de gestão: descentralizar a distribuição de hormônio para pessoas trans (hoje concentrada em uma única farmácia da cidade), direcionar busca ativa de prevenção ao câncer de colo do útero e cursos de Libras por território, e identificar erros de cadastro a partir de padrões espaciais. O escopo é a Atenção Básica (ACS/UBS); o Serviço de Atenção Domiciliar (SAD) fica fora.

**Situação atual**: o acesso ao PEC/e-SUS ainda não foi liberado pela Secretaria.

## Nossa solução

Um pipeline de dados em camadas (arquitetura medalhão), desenhado para funcionar hoje com fontes públicas reais e uma camada de dados **fictícios/simulados** — com a mesma estrutura do PEC real — e para absorver o PEC de verdade, sem redesenho, no momento em que o acesso for liberado. Enquanto isso, o pipeline já entrega: uma base territorial real (unidades, equipes, distritos), mapas de calor e ranking de completude sobre dados simulados, e um agente de consulta em linguagem natural — tudo pronto para receber o dado real no lugar do fictício.

## Arquitetura

```
                              APIs públicas (CNES, IBGE, Dados Recife)
                                              │
                                arquivos JSON locais (bronze)
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    │                                                   │
        MongoDB Atlas (bronze) ◄────────── gerador de dados fictícios (src/mock/)
                    │                       estrutura real do PEC, dados simulados
                    │
      transformação e limpeza (silver)
                    │
          Neon / PostgreSQL (silver)
                    │
      ┌─────────────┴─────────────┐
      │                           │
Dashboard (Streamlit + Plotly + Folium)   Agente de perguntas em linguagem
                                           natural (Ollama, local, sem API paga)
```

- **Extração (`src/extract/`)**: um script por fonte pública, que consulta a API e salva o resultado bruto em `data/bronze/<fonte>/`, sem transformação.
- **Simulação (`src/mock/`)**: gera dados **fictícios** com a estrutura real do PEC (raça/cor, deficiência, orientação sexual e identidade de gênero com o filtro de duas etapas, exclusão de crianças de 0 a 10 anos), ancorados nas equipes/unidades/distritos reais do CNES. Não é extração — não existe fonte real por trás.
- **Carga bronze (`src/load_bronze/`)**: lê os arquivos (reais e fictícios) e insere cada um em uma coleção no MongoDB Atlas, com metadados de rastreabilidade (`_meta`) — coleções fictícias recebem também um aviso explícito (`_meta.aviso`).
- **Transformação silver (`src/transform/`)**: lê as coleções do MongoDB, limpa e organiza os dados em tabelas relacionais no Neon/PostgreSQL. Separado em dois scripts: um para os dados reais, outro para os fictícios.
- **Agente (`src/agent/`)**: responde perguntas em português sobre os dados do Neon, usando um LLM local (Ollama) para gerar SQL — sem depender de nenhuma API paga.

## Fontes de dados reais utilizadas

Nenhuma das fontes abaixo é o PEC/e-SUS. São fontes **públicas**, usadas para construir a dimensão de território, unidade de saúde e o "baseline" populacional.

### 1. CNES — Cadastro Nacional de Estabelecimentos de Saúde
**Plataforma**: `cnes.datasus.gov.br` (Ministério da Saúde / DATASUS)

| Dataset | Volume | Conteúdo |
|---|---|---|
| Estabelecimentos de saúde do Recife (CNES, extração 2026-10-16 UTC) | 4.726 unidades (525 atendem SUS) | Nome, código CNES, endereço, distrito sanitário |
| Equipes de Saúde da Família | 827 equipes (433 do tipo ESF) | Tipo de equipe, unidade vinculada, status de ativação |

**Papel no projeto**: dimensão "Unidade" e "Equipe" — usa o mesmo código CNES que o PEC utiliza, e é a base territorial sobre a qual a camada de simulação (e futuramente o PEC real) se apoia.

### 2. IBGE — Censo Demográfico (via API SIDRA)
**Ano de referência**: 2022

| Dataset | Conteúdo |
|---|---|
| População do Recife por raça/cor | Branca, Preta, Parda, Amarela, Indígena |
| População do Recife com deficiência, por tipo | 5 tipos de dificuldade + total oficial |

**Papel no projeto**: linha de base populacional real da cidade — referência ("esperado") para comparar com o que for observado nos atendimentos.

**Limitação conhecida**: só disponível a nível de município inteiro, não por distrito — por isso a distribuição por Distrito Sanitário (usada no mapa de gap racial) é, por ora, simulada (ver seção de dados fictícios).

**Premissa operacional de Atenção Básica**: além dos dados oficiais do Censo, o projeto aceita um cenário de planejamento para dimensionamento de cobertura e priorização de equipes: 80% da população do Recife é assumida como público atendido pela Atenção Básica; 11,1% da população total é usada como referência de deficiência; população negra como Pretos + Pardos = 60,8%, distribuída em 48,5% pardos e 12,3% pretos; brancos = 38,8%; o restante corresponde a indígenas e amarelos; 4% do público de Atenção Básica é usado como referência para estimativa LGBTQIA+. A soma de pardos e pretos resulta em 60,8%. Esse cenário é uma hipótese operacional de gestão e não substitui os percentuais oficiais do Censo IBGE.

No mapa de Contexto Territorial, os totais municipais desse cenário são distribuídos entre os distritos proporcionalmente à população distrital simulada, com uma ponderação territorial ilustrativa (fator de 0,8 a 1,2) que prioriza áreas mais distantes do litoral e do centro. A aproximação usa a posição oeste-leste dos distritos como proxy de distância do litoral e a distância ao Marco Zero como proxy de distância do centro; não mede a distância real de cada pessoa nem representa uma distribuição oficial por distrito. O hover mostra percentuais dentro do distrito: pessoas negras, pardas, pretas e PCD sobre a população residente estimada; pessoas LGBTQIA+ sobre a população local estimada da Atenção Básica (80% da população residente). Os totais municipais permanecem compatíveis com 60,8% de pessoas negras (48,5% pardas e 12,3% pretas), 11,1% de PCD e 4% de LGBTQIA+ sobre o público de Atenção Básica.

O arquivo `data/bronze/dados_recife/macroregiao_de_saude_recife.csv` contém a linha de Recife extraída do CSV de macrorregiões de saúde. Ela informa a Região de Saúde I, a macrorregião Metropolitana e a população IBGE 2022 de **1.488.920 habitantes**. Esse arquivo não contém estabelecimentos; os totais de **4.726 estabelecimentos** (dos quais **525 atendem SUS**) vêm da extração do CNES em 2026-10-16 UTC. O dashboard mostra essas quantidades separadamente e usa a população do arquivo para a estimativa ilustrativa de 4% LGBTQIA+, conferida com o Censo 2022.

### 3. Dados Recife (Portal de Dados Abertos da Prefeitura)

| Dataset | Volume | Conteúdo |
|---|---|---|
| Distritos Sanitários do Recife (geometria) | 8 distritos | Polígonos geográficos de cada Distrito Sanitário |
| Distritos Sanitários — bairros | 94 bairros | Mapeamento de bairro → Distrito Sanitário |

**Papel no projeto**: base geográfica para os mapas de calor e de gap.

## Dados fictícios/simulados (`src/mock/`)

**Importante**: os dados abaixo são 100% fictícios. Não representam pacientes, atendimentos ou população real de Recife. Foram gerados para testar o pipeline (mapas, indicadores, modelo de ML) enquanto o PEC/e-SUS real não é liberado, seguindo a estrutura real descrita pela Secretaria.

| Dataset | Volume | Conteúdo |
|---|---|---|
| Atendimentos simulados | ~54.800 registros | Um atendimento por linha, ligado a uma equipe ESF real; raça/cor, deficiência, orientação sexual e identidade de gênero seguindo a lógica real do PEC (incluindo a possibilidade de campo vazio, simulando o sub-registro) |
| População negra esperada por distrito | 8 distritos | Percentual ilustrativo, usado como referência ("esperado") no mapa de gap racial |

**Regra de negócio replicada**: atendimentos de pacientes com menos de 10 anos não têm orientação sexual/identidade de gênero preenchidos — mesma exclusão adotada pela Secretaria.

**Desigualdade simulada de propósito**: cada equipe tem uma taxa de completude diferente, para que o ranking de piores equipes (usado para priorizar capacitação) tenha algo real para ordenar, em vez de todas as equipes terem o mesmo número por acaso.

Gerado por `src/mock/gerar_mock_pec.py`, que lê as equipes ESF reais e ativas no Neon para ancorar a simulação na estrutura territorial verdadeira.

### Formulários individuais PEC simulados

O script `src/mock/gerar_banco_formulario_pec.py` gera `data/bronze/mock_pec/pec_formulario_recife.sqlite`, com **1.191.136 registros sintéticos por padrão**, equivalentes a 80% da população municipal de referência de 1.488.920 pessoas. `--registros` pode ser usado para execuções reduzidas de teste; nesse caso, o cadastro não representa o total de 80%. O schema acompanha campos da Ficha de Cadastro Individual PEC/e-SUS APS v5.31, incluindo identificação, sexo, raça/cor, escolaridade, orientação sexual, identidade de gênero, deficiência, segurança alimentar e condições autorreferidas de saúde.

O banco tem as tabelas `cadastro_pec`, `enderecos_por_distrito`, `distrito_populacao` e `metadados_simulacao`. Os bairros são associados aos Distritos Sanitários pelo mapeamento público local; logradouros e números são marcados como simulados, e CEP, CNS, CPF, NIS, CNES e identificadores profissionais não são inventados. Os formulários e valores pessoais não representam moradores reais.

Os 1.191.136 formulários representam, no cenário, 80% de 1.488.920 habitantes. O sexo foi distribuído segundo o Censo 2022 do IBGE/SIDRA para Recife (tabela 9514): 683.536 homens e 805.384 mulheres na população total, resultando em 546.829 registros `M` e 644.307 registros `F` na população simulada; `I` fica em zero porque a fonte censitária usada não apresenta essa categoria. A deficiência usa 11,1% do grupo simulado (132.216 formulários); raça/cor usa as proporções informadas: 38,8% branca, 12,3% preta, 48,5% parda e os 0,4% restantes divididos igualmente entre amarelos e indígenas. Isso produz cerca de 462.161 brancos, 146.510 pretos, 577.701 pardos, 2.382 amarelos e 2.382 indígenas. LGBTQIA+ usa 4% do grupo de Atenção Básica (47.645 registros).

Os pesos de população por distrito (14%, 12%, 11%, 12%, 15%, 11%, 13%, 12%) continuam **ilustrativos**, pois o repositório não dispõe da população oficial por Distrito Sanitário; portanto, a quantidade por distrito não deve ser apresentada como dado do IBGE. Os totais por sexo, raça/cor e deficiência são controlados para fechar no total municipal simulado e também distribuídos entre os distritos segundo esses pesos provisórios. Os formulários não representam pessoas reais. Condições de saúde e campos sem proporções fornecidas são valores aleatórios de demonstração, sem validade epidemiológica.

Para gerar/regerar a base completa: `python src/mock/gerar_banco_formulario_pec.py`. Para uma execução menor de teste: `python src/mock/gerar_banco_formulario_pec.py --registros 10000`. A execução reconstrói apenas as tabelas gerenciadas pelo script nesse arquivo SQLite.

## Banco de dados (MongoDB Atlas — camada bronze)

**Banco**: `bronze_equidade_saude`

| Coleção | Documentos | Fonte |
|---|---|---|
| `cnes_estabelecimentos` | 4.726 | real |
| `cnes_estabelecimentos_detalhe` | 525 | real |
| `cnes_equipes` | 827 | real |
| `ibge_censo_raca_cor` | 7 | real |
| `ibge_censo_deficiencia_tipo` | 19 | real |
| `dados_recife_distritos_geometria` | 1 (GeoJSON) | real |
| `dados_recife_distritos_bairros` | 94 | real |
| `mock_pec_atendimentos` | ~54.800 | **fictício** |
| `mock_populacao_negra_distrito` | 8 | **fictício** |

## Banco de dados (Neon/PostgreSQL — camada silver)

| Tabela | Linhas | Fonte | Conteúdo |
|---|---|---|---|
| `unidades_saude` | 525 | real | Unidades de saúde, distrito, bairro, endereço, coordenadas |
| `equipes_saude` | 827 | real | Equipes vinculadas a cada unidade, com status de ativação |
| `censo_raca_cor` | 5 | real | População do Recife por raça/cor (Censo 2022) |
| `censo_deficiencia` | 6 | real | População do Recife por tipo de deficiência (Censo 2022) + total oficial (`e_total`) |
| `mock_pec_atendimentos` | ~54.800 | **fictício** | Atendimentos simulados por equipe, com os campos sensíveis do PEC |
| `mock_populacao_negra_distrito` | 8 | **fictício** | Percentual esperado de população negra por distrito (referência do mapa de gap) |

As duas tabelas fictícias têm um `COMMENT ON TABLE` no próprio banco avisando que são simuladas — qualquer pessoa consultando o Neon direto vê o aviso.

**Achado de qualidade de dados (dado real)**: uma parte das unidades de saúde não tem `distrito_sanitario_codigo` preenchido no CNES (hospitais, laboratórios e outros estabelecimentos que não pertencem a um Distrito Sanitário). Essa lacuna foi mantida — não "corrigida" — porque é uma inconsistência real que a Secretaria precisa ver e resolver na fonte.

**Cuidado estatístico**: em `censo_deficiencia`, os tipos de dificuldade não são mutuamente exclusivos — por isso a coluna `e_total` identifica a linha com o total oficial, que não deve ser recalculado somando as categorias.

## Agente de perguntas em linguagem natural

Permite perguntar em português sobre os dados do Neon e receber uma resposta direta. Roda 100% local, sem API paga:

1. O LLM local (`llama3.2`, via [Ollama](https://ollama.com)) traduz a pergunta em SQL.
2. O SQL é executado no Neon (só `SELECT` é permitido, por segurança).
3. Resultado de um único número é formatado direto pelo código (mais confiável); resultados com várias linhas passam pelo LLM para virar uma frase. Se a pergunta envolver as tabelas fictícias, a resposta inclui um aviso de dado simulado.

Arquivos: `src/agent/assistente.py` (motor) e `src/agent/app_streamlit.py` (interface web).

## Interface gráfica (Streamlit + Plotly + Folium)

A interface EquiDados reúne o dashboard territorial e o assistente em uma única aplicação, com navegação lateral e filtros organizados em duas linhas para distrito, equipe, unidade, raça/cor, identidade de gênero, orientação sexual e deficiência:

- **Painel de Equidade**: indicadores de atendimentos, equipes, cobertura territorial e completude; mapas de concentração LGBTQIAPN+, PCD e diferença racial ilustrativa; ranking de equipes.
- **Monitor de Cadastro**: ranking de completude, evolução temporal, distribuição de raça/cor por distrito e situação do preenchimento de orientação sexual.
- **Contexto Territorial**: mapa interativo com GeoPandas, Folium e Streamlit-Folium — limites dos oito Distritos Sanitários, marcadores agrupados de unidades de saúde, pop-ups de CNES e filtro por distrito no seletor. Ao passar o mouse sobre um distrito, o mapa resume unidades mapeadas e farmácias da planilha anexada; ao clicar, abre a relação detalhada das unidades e farmácias associadas à área. A planilha inclui CNPJ, nome, logradouro e bairro para 52 farmácias; como não fornece coordenadas, cada farmácia é associada ao distrito pelo bairro e os marcadores laranja indicam apenas a área, não a localização exata da loja. Os pontos das unidades são criados em EPSG:4326 e associados aos polígonos por junção espacial; unidades sem coordenadas não são desenhadas. A página também apresenta CNES e Censo por categoria, unidades sem distrito informado e percentuais censitários com denominadores explícitos. População negra = Preta + Parda; percentual de deficiência usa a população com 2 anos ou mais. Inclui uma estimativa ilustrativa LGBTQIA+ calculada com a taxa de referência de 4% e a população-base informadas para o cenário; ela não é uma contagem do Censo, e a interface destaca a diferença entre essa população-base e o total do Censo 2022 disponível no projeto.
- **Assistente EquiDados**: perguntas em português respondidas pelo Ollama local com consulta ao Neon.
- **Dados e consultas SQL**: quatro consultas SQL explícitas (incluindo junções entre tabelas), visualização dos resultados em tabelas e gráficos e consulta paginada das tabelas do CNES, Censo, dados simulados e visões analíticas. A interface também permite inserir, alterar e excluir nas tabelas fictícias `mock_pec_atendimentos` e `mock_populacao_negra_distrito`; as tabelas reais do CNES e do Censo ficam somente para consulta.
- **Etapa 04 — Consultas Avançadas, Visões e Índices**: script [Etapa_04_Consultas_Avancadas.sql](./Etapa_04_Consultas_Avancadas.sql) com dois índices compostos usados pelos filtros recentes por equipe/data e data/distrito; quatro consultas novas (anti join, full outer join e duas com subconsultas); e duas visões de domínio, cada uma relacionando pelo menos três conjuntos por JOIN. As visões consolidam indicadores territoriais e completude por equipe; dados `mock_` e referências distritais continuam identificados como simulados. A interface também disponibiliza as quatro consultas avançadas e permite consultar as visões em **Dados e consultas SQL → Consultas e gráficos**.

As telas de Machine Learning e recomendações territoriais do wireframe não estão incluídas: o projeto ainda não implementa um modelo de previsão nem uma lógica de recomendação. Os dados de atendimentos e a referência de população negra por distrito continuam identificados como simulados.

Arquivo principal: `src/dashboard/app_dashboard.py`. O GeoPandas consta em `requirements.txt` e é utilizado para validar coordenadas e associar espacialmente unidades aos distritos.

## Estrutura de pastas

```
Projeto - BD/
├── .env                            # credenciais (MongoDB, Neon) — não versionado
├── requirements.txt
├── arquivo.sql                     # esquema inicial e consultas da aplicação
├── Etapa_04_Consultas_Avancadas.sql # índices, consultas avançadas e visões
├── data/
│   └── bronze/
│       ├── cnes/
│       ├── ibge/
│       ├── dados_recife/
│       └── mock_pec/               # dados fictícios gerados
└── src/
    ├── extract/                    # um script por fonte pública
    │   ├── cnes_estabelecimentos.py
    │   ├── cnes_estabelecimentos_detalhe.py
    │   ├── cnes_equipes.py
    │   ├── ibge_censo_raca_cor.py
    │   ├── ibge_censo_deficiencia.py
    │   ├── dados_recife_distritos_geometria.py
    │   └── dados_recife_distritos_bairros.py
    ├── mock/
    │   └── gerar_mock_pec.py       # gera os dados fictícios com estrutura real do PEC
    ├── load_bronze/
    │   └── carregar_mongo.py       # sobe os arquivos (reais e fictícios) para o MongoDB
    ├── transform/
    │   ├── mongo_para_neon.py      # tabelas reais: Mongo (bronze) → Neon (silver)
    │   └── mongo_para_neon_mock.py # tabelas fictícias: Mongo (bronze) → Neon (silver)
    ├── agent/
    │   ├── assistente.py           # motor do agente (SQL + resposta via Ollama)
    │   ├── app_streamlit.py        # interface web do agente
    │   └── testar_ollama.py        # script de teste da conexão com o Ollama
    ├── dashboard/
    │   ├── app_dashboard.py        # dashboard integrado (Streamlit + Plotly + Folium)
    │   └── pagina_dados.py         # CRUD dos mocks e consultas SQL com gráficos
    └── utils/
        ├── testar_conexao_mongo.py
        ├── testar_conexao_neon.py
        └── gerar_kickoff_pptx.py   # gera os slides do kick-off (python-pptx)
```

## Como rodar

### Se você só vai apresentar (interface integrada, dados já estão no Neon compartilhado)

Não precisa rodar nenhum script de extração/carga — os dados (reais e fictícios) já estão no banco Neon compartilhado pelo grupo. Só precisa:

```bash
# 1. Clonar o repositório
git clone git@github.com:fccbl/etl-equidade-saude-recife.git
cd etl-equidade-saude-recife

# 2. Criar ambiente virtual e instalar dependências
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Copiar .env.example para .env e preencher localmente as credenciais necessárias
Copy-Item .env.example .env  # PowerShell
# Configure NEON_DATABASE_URL e MONGO_URI dentro do arquivo .env

# 4. Instalar o Ollama (https://ollama.com) e baixar o modelo local — só na primeira vez
ollama pull llama3.2

# 5. Rodar a interface integrada (painel, monitor, contexto e assistente)
streamlit run src/dashboard/app_dashboard.py
```

⚠️ O `.env` **não vem no repositório** (fica de fora por segurança). A interface e o assistente precisam de `NEON_DATABASE_URL`; o pipeline que usa MongoDB também precisa de `MONGO_URI`. Configure as credenciais localmente e nunca as envie ao Git ou a conversas públicas.

O painel "Insights de ML" usa a coluna `turno_atendimento`. Se o Neon compartilhado
ainda tiver a versão antiga da tabela, atualize o mock antes de abrir a página:

```bash
python src/mock/gerar_mock_pec.py
python src/load_bronze/carregar_mongo.py
python src/transform/mongo_para_neon_mock.py
```

Isso recria os atendimentos sintéticos com turno. A ausência de raça/cor ou
deficiência não informa se o dado não foi perguntado ou se a pessoa preferiu não
responder; não interprete esses rótulos simulados como causa confirmada.

O assistente pode continuar sendo executado isoladamente, se necessário, com
`streamlit run src/agent/app_streamlit.py`.

### Pipeline completo, do zero (extração + carga + geração do mock)

```bash
# 1. Extrair os dados reais das APIs públicas
python src/extract/cnes_estabelecimentos.py
python src/extract/cnes_estabelecimentos_detalhe.py
python src/extract/cnes_equipes.py
python src/extract/ibge_censo_raca_cor.py
python src/extract/ibge_censo_deficiencia.py
python src/extract/dados_recife_distritos_geometria.py
python src/extract/dados_recife_distritos_bairros.py

# 2. Carregar os dados reais no MongoDB (bronze) e transformar no Neon (silver)
python src/load_bronze/carregar_mongo.py
python src/transform/mongo_para_neon.py

# 3. Gerar os dados fictícios (precisa das equipes reais já carregadas no Neon)
python src/mock/gerar_mock_pec.py

# 4. Carregar os dados fictícios no MongoDB e transformar no Neon
python src/load_bronze/carregar_mongo.py
python src/transform/mongo_para_neon_mock.py

# 5. Rodar a interface integrada (painel, monitor, insights de ML e assistente)
ollama pull llama3.2          # uma vez só, baixa o modelo local
streamlit run src/dashboard/app_dashboard.py
```

O assistente também pode ser executado separadamente por compatibilidade:
`streamlit run src/agent/app_streamlit.py`.

## Próximas etapas

1. **Modelo demonstrativo de Machine Learning**: a página "Insights de ML" treina regressão logística para estimar risco de não preenchimento por campo, usando janela móvel de três meses e validação no mês seguinte, nos dados simulados. A base de atendimentos precisa ser gerada novamente para incluir `turno_atendimento`; a avaliação simulada não mede desempenho real.
2. **Integração e validação com o PEC/e-SUS APS real**: pendente de autorização da Secretaria. Antes de qualquer uso operacional, validar a definição de ausência/recusa, a qualidade dos rótulos e o desempenho temporal e por grupos; manter revisão humana e não usar alertas para avaliar individualmente profissionais ou pressionar pacientes.
