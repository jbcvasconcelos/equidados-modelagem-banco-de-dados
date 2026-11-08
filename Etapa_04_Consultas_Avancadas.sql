-- ETAPA 04 - Consultas avancadas, visoes e indices
-- Banco: PostgreSQL / Neon
-- As tabelas mock_ contem dados ficticios/simulados.
--
-- Os indices atendem os filtros por equipe/data e data/distrito das
-- consultas de atividade recente e dos indicadores territoriais.
-- Execute este arquivo conectado ao banco EquiDados.

BEGIN;

CREATE INDEX IF NOT EXISTS idx_mock_atendimentos_equipe_data_etapa04
    ON mock_pec_atendimentos (codigo_equipe, data_atendimento);

CREATE INDEX IF NOT EXISTS idx_mock_atendimentos_data_distrito_etapa04
    ON mock_pec_atendimentos (data_atendimento, distrito_sanitario_codigo);

-- Visao 1: consolidado territorial de capacidade, atendimentos e equidade.
-- Justificativa semantica: a gestao pode comparar, por distrito, a estrutura
-- de unidades e equipes com os atendimentos simulados, completude de raca/cor
-- e a referencia territorial ilustrativa. Os agregados sao calculados antes
-- dos JOINs para evitar multiplicar contagens entre unidades e atendimentos.
-- A visao realiza cinco LEFT JOINs entre agregados de dominio relacionados.
CREATE OR REPLACE VIEW vw_equidade_distrital AS
WITH distritos AS (
    SELECT distrito_sanitario_codigo
    FROM unidades_saude
    WHERE distrito_sanitario_codigo IS NOT NULL
    UNION
    SELECT distrito_sanitario_codigo
    FROM mock_pec_atendimentos
    WHERE distrito_sanitario_codigo IS NOT NULL
    UNION
    SELECT distrito_sanitario_codigo
    FROM mock_populacao_negra_distrito
),
unidades AS (
    SELECT distrito_sanitario_codigo,
           COUNT(DISTINCT cnes) AS total_unidades
    FROM unidades_saude
    WHERE distrito_sanitario_codigo IS NOT NULL
    GROUP BY distrito_sanitario_codigo
),
equipes AS (
    SELECT u.distrito_sanitario_codigo,
           COUNT(DISTINCT e.codigo_equipe) AS total_equipes
    FROM equipes_saude e
    JOIN unidades_saude u ON u.cnes = e.cnes_unidade
    WHERE u.distrito_sanitario_codigo IS NOT NULL
    GROUP BY u.distrito_sanitario_codigo
),
atendimentos AS (
    SELECT distrito_sanitario_codigo,
           COUNT(*) AS total_atendimentos_simulados,
           COUNT(raca_cor) AS registros_com_raca_cor,
           COUNT(*) FILTER (
               WHERE raca_cor IN ('Preta', 'Parda')
           ) AS registros_pretos_ou_pardos,
           COUNT(*) FILTER (
               WHERE idade >= 10
           ) AS atendimentos_com_10_anos_ou_mais
    FROM mock_pec_atendimentos
    WHERE distrito_sanitario_codigo IS NOT NULL
    GROUP BY distrito_sanitario_codigo
),
atendimentos_recentes AS (
    SELECT distrito_sanitario_codigo,
           COUNT(*) AS atendimentos_ultimos_90_dias
    FROM mock_pec_atendimentos
    WHERE data_atendimento >= CURRENT_DATE - INTERVAL '90 days'
      AND data_atendimento < CURRENT_DATE + INTERVAL '1 day'
      AND distrito_sanitario_codigo IS NOT NULL
    GROUP BY distrito_sanitario_codigo
)
SELECT d.distrito_sanitario_codigo,
       COALESCE(u.total_unidades, 0) AS total_unidades,
       COALESCE(e.total_equipes, 0) AS total_equipes,
       COALESCE(a.total_atendimentos_simulados, 0)
           AS total_atendimentos_simulados,
       COALESCE(ar.atendimentos_ultimos_90_dias, 0)
           AS atendimentos_ultimos_90_dias,
       COALESCE(a.registros_com_raca_cor, 0) AS registros_com_raca_cor,
       ROUND(
           100.0 * COALESCE(a.registros_com_raca_cor, 0)
               / NULLIF(a.total_atendimentos_simulados, 0),
           1
       ) AS completude_raca_cor_pct,
       ROUND(
           100.0 * a.registros_pretos_ou_pardos
               / NULLIF(a.registros_com_raca_cor, 0),
           1
       ) AS percentual_preto_ou_pardo_observado,
       ROUND(100.0 * p.populacao_negra_pct_esperado, 1)
           AS percentual_preto_ou_pardo_referencia_simulada,
       ROUND(
           100.0 * p.populacao_negra_pct_esperado
               - 100.0 * a.registros_pretos_ou_pardos
                   / NULLIF(a.registros_com_raca_cor, 0),
           1
       ) AS diferenca_referencia_observado_pontos_percentuais,
       COALESCE(a.atendimentos_com_10_anos_ou_mais, 0)
           AS atendimentos_com_10_anos_ou_mais
FROM distritos d
LEFT JOIN unidades u
    ON u.distrito_sanitario_codigo = d.distrito_sanitario_codigo
LEFT JOIN equipes e
    ON e.distrito_sanitario_codigo = d.distrito_sanitario_codigo
LEFT JOIN atendimentos a
    ON a.distrito_sanitario_codigo = d.distrito_sanitario_codigo
LEFT JOIN atendimentos_recentes ar
    ON ar.distrito_sanitario_codigo = d.distrito_sanitario_codigo
LEFT JOIN mock_populacao_negra_distrito p
    ON p.distrito_sanitario_codigo = d.distrito_sanitario_codigo;

COMMENT ON VIEW vw_equidade_distrital IS
    'Consolida estrutura de saude, atendimentos simulados e indicadores '
    'territoriais de completude/equidade por distrito. A referencia e '
    'ilustrativa, nao representa estimativa oficial.';

-- Visao 2: completude e volume por equipe, unidade e distrito.
-- Justificativa semantica: equipes de gestao podem priorizar apoio e
-- capacitacao a partir do volume e da completude dos registros. A referencia
-- distrital serve de contexto, sem classificar desempenho individual.
-- A visao relaciona equipe, unidade, atendimentos agregados e referencia
-- distrital (tres LEFT JOINs).
CREATE OR REPLACE VIEW vw_completude_por_equipe AS
WITH atendimentos_equipe AS (
    SELECT codigo_equipe,
           COUNT(*) AS total_atendimentos_simulados,
           COUNT(raca_cor) AS registros_com_raca_cor,
           COUNT(deficiencia_tipo) AS registros_com_deficiencia,
           COUNT(*) FILTER (
               WHERE idade >= 10
           ) AS atendimentos_com_10_anos_ou_mais,
           COUNT(orientacao_sexual) FILTER (
               WHERE idade >= 10
           ) AS registros_com_orientacao_sexual,
           COUNT(identidade_genero) FILTER (
               WHERE idade >= 10
           ) AS registros_com_identidade_genero,
           MAX(data_atendimento) AS data_ultimo_atendimento
    FROM mock_pec_atendimentos
    WHERE codigo_equipe IS NOT NULL
    GROUP BY codigo_equipe
)
SELECT e.codigo_equipe,
       e.nome_equipe,
       e.tipo_equipe,
       u.cnes AS cnes_unidade,
       COALESCE(u.nome_fantasia, u.nome_empresarial) AS unidade,
       u.distrito_sanitario_codigo,
       COALESCE(a.total_atendimentos_simulados, 0)
           AS total_atendimentos_simulados,
       a.data_ultimo_atendimento,
       ROUND(
           100.0 * a.registros_com_raca_cor
               / NULLIF(a.total_atendimentos_simulados, 0),
           1
       ) AS completude_raca_cor_pct,
       ROUND(
           100.0 * a.registros_com_deficiencia
               / NULLIF(a.total_atendimentos_simulados, 0),
           1
       ) AS completude_deficiencia_pct,
       ROUND(
           100.0 * a.registros_com_orientacao_sexual
               / NULLIF(a.atendimentos_com_10_anos_ou_mais, 0),
           1
       ) AS completude_orientacao_sexual_10_mais_pct,
       ROUND(
           100.0 * a.registros_com_identidade_genero
               / NULLIF(a.atendimentos_com_10_anos_ou_mais, 0),
           1
       ) AS completude_identidade_genero_10_mais_pct,
       ROUND(100.0 * p.populacao_negra_pct_esperado, 1)
           AS percentual_negro_referencia_distrital_simulada
FROM equipes_saude e
LEFT JOIN unidades_saude u
    ON u.cnes = e.cnes_unidade
LEFT JOIN atendimentos_equipe a
    ON a.codigo_equipe = e.codigo_equipe
LEFT JOIN mock_populacao_negra_distrito p
    ON p.distrito_sanitario_codigo = u.distrito_sanitario_codigo;

COMMENT ON VIEW vw_completude_por_equipe IS
    'Completude agregada de registros ficticios por equipe, com contexto da '
    'unidade e referencia territorial simulada. Nao deve ser usada para '
    'avaliar individualmente profissionais.';

COMMIT;

-- CONSULTA 1 - ANTI JOIN (LEFT JOIN + IS NULL)
-- Equipes ativas sem atendimentos simulados nos ultimos 90 dias.
-- A data de corte e relativa ao dia de execucao.
SELECT e.codigo_equipe,
       e.nome_equipe,
       e.tipo_equipe,
       u.cnes AS cnes_unidade,
       COALESCE(u.nome_fantasia, u.nome_empresarial) AS unidade,
       u.distrito_sanitario_codigo
FROM equipes_saude e
LEFT JOIN unidades_saude u
    ON u.cnes = e.cnes_unidade
LEFT JOIN mock_pec_atendimentos a
    ON a.codigo_equipe = e.codigo_equipe
   AND a.data_atendimento >= CURRENT_DATE - INTERVAL '90 days'
   AND a.data_atendimento <= CURRENT_DATE
WHERE NULLIF(BTRIM(e.data_desativacao), '') IS NULL
  AND a.id_atendimento IS NULL
ORDER BY u.distrito_sanitario_codigo, e.codigo_equipe;

-- CONSULTA 2 - FULL OUTER JOIN
-- Compara distritos que aparecem na estrutura CNES com distritos que possuem
-- atendimentos simulados, mantendo categorias presentes em apenas uma fonte.
WITH unidades_por_distrito AS (
    SELECT distrito_sanitario_codigo,
           COUNT(DISTINCT cnes) AS total_unidades
    FROM unidades_saude
    WHERE distrito_sanitario_codigo IS NOT NULL
    GROUP BY distrito_sanitario_codigo
),
atendimentos_por_distrito AS (
    SELECT distrito_sanitario_codigo,
           COUNT(*) AS atendimentos_ultimos_90_dias
    FROM mock_pec_atendimentos
    WHERE data_atendimento >= CURRENT_DATE - INTERVAL '90 days'
      AND data_atendimento < CURRENT_DATE + INTERVAL '1 day'
      AND distrito_sanitario_codigo IS NOT NULL
    GROUP BY distrito_sanitario_codigo
)
SELECT COALESCE(
           u.distrito_sanitario_codigo,
           a.distrito_sanitario_codigo
       ) AS distrito_sanitario_codigo,
       COALESCE(u.total_unidades, 0) AS total_unidades,
       COALESCE(a.atendimentos_ultimos_90_dias, 0)
           AS atendimentos_ultimos_90_dias,
       CASE
           WHEN u.distrito_sanitario_codigo IS NULL
               THEN 'Somente atendimentos simulados'
           WHEN a.distrito_sanitario_codigo IS NULL
               THEN 'Somente estrutura CNES'
           ELSE 'Estrutura CNES e atendimentos simulados'
       END AS origem_dos_registros
FROM unidades_por_distrito u
FULL OUTER JOIN atendimentos_por_distrito a
    ON a.distrito_sanitario_codigo = u.distrito_sanitario_codigo
ORDER BY distrito_sanitario_codigo;

-- CONSULTA 3 - SUBCONSULTA ESCALAR
-- Equipes com volume acima da media entre equipes com atendimentos.
WITH atendimentos_por_equipe AS (
    SELECT codigo_equipe, COUNT(*) AS total_atendimentos
    FROM mock_pec_atendimentos
    WHERE codigo_equipe IS NOT NULL
    GROUP BY codigo_equipe
)
SELECT e.codigo_equipe,
       e.nome_equipe,
       COALESCE(u.nome_fantasia, u.nome_empresarial) AS unidade,
       a.total_atendimentos
FROM atendimentos_por_equipe a
JOIN equipes_saude e ON e.codigo_equipe = a.codigo_equipe
LEFT JOIN unidades_saude u ON u.cnes = e.cnes_unidade
WHERE a.total_atendimentos > (
    SELECT AVG(media.total_atendimentos)
    FROM atendimentos_por_equipe media
)
ORDER BY a.total_atendimentos DESC, e.codigo_equipe;

-- CONSULTA 4 - SUBCONSULTA ESCALAR
-- Distritos cuja proporcao observada de registros pretos/pardos supera a
-- proporcao municipal observada nos atendimentos simulados.
WITH atendimentos_por_distrito AS (
    SELECT distrito_sanitario_codigo,
           COUNT(raca_cor) AS registros_com_raca_cor,
           COUNT(*) FILTER (
               WHERE raca_cor IN ('Preta', 'Parda')
           ) AS registros_pretos_ou_pardos
    FROM mock_pec_atendimentos
    WHERE distrito_sanitario_codigo IS NOT NULL
    GROUP BY distrito_sanitario_codigo
)
SELECT distrito_sanitario_codigo,
       registros_com_raca_cor,
       registros_pretos_ou_pardos,
       ROUND(
           100.0 * registros_pretos_ou_pardos
               / NULLIF(registros_com_raca_cor, 0),
           1
       ) AS percentual_preto_ou_pardo_distrital
FROM atendimentos_por_distrito
WHERE registros_com_raca_cor > 0
  AND 1.0 * registros_pretos_ou_pardos / registros_com_raca_cor > (
      SELECT 1.0 * COUNT(*) FILTER (
          WHERE raca_cor IN ('Preta', 'Parda')
      ) / NULLIF(COUNT(raca_cor), 0)
      FROM mock_pec_atendimentos
  )
ORDER BY percentual_preto_ou_pardo_distrital DESC;
