-- EquiDados: esquema PostgreSQL/Neon e consultas da interface.
-- Os dados das tabelas mock_ sao ficticios/simulados.
-- Este script cria a estrutura e executa apenas consultas SELECT ao final.

BEGIN;

CREATE TABLE IF NOT EXISTS unidades_saude (
    cnes                      TEXT PRIMARY KEY,
    nome_fantasia             TEXT,
    nome_empresarial          TEXT,
    bairro                    TEXT,
    distrito_sanitario_codigo TEXT,
    distrito_sanitario_nome   TEXT,
    endereco                  TEXT,
    cep                       TEXT,
    latitude                  DOUBLE PRECISION,
    longitude                 DOUBLE PRECISION,
    tipo_estabelecimento      TEXT
);

CREATE TABLE IF NOT EXISTS equipes_saude (
    codigo_equipe    TEXT PRIMARY KEY,
    nome_equipe      TEXT,
    tipo_equipe      TEXT,
    cnes_unidade     TEXT REFERENCES unidades_saude(cnes),
    data_ativacao    TEXT,
    data_desativacao TEXT
);

CREATE TABLE IF NOT EXISTS censo_raca_cor (
    raca_cor  TEXT PRIMARY KEY,
    populacao BIGINT,
    ano       INTEGER
);

CREATE TABLE IF NOT EXISTS censo_deficiencia (
    tipo_dificuldade TEXT PRIMARY KEY,
    populacao        BIGINT,
    ano              INTEGER,
    e_total          BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS mock_pec_atendimentos (
    id_atendimento                    INTEGER PRIMARY KEY,
    codigo_equipe                     TEXT REFERENCES equipes_saude(codigo_equipe),
    cnes_unidade                      TEXT REFERENCES unidades_saude(cnes),
    distrito_sanitario_codigo         TEXT,
    data_atendimento                  DATE,
    tipo_atendimento                  TEXT,
    profissional_tipo                 TEXT,
    turno_atendimento                 TEXT,
    idade                             INTEGER,
    raca_cor                          TEXT,
    deficiencia_tipo                  TEXT,
    deseja_informar_orientacao_sexual TEXT,
    orientacao_sexual                 TEXT,
    deseja_informar_identidade_genero TEXT,
    identidade_genero                 TEXT,
    nome_social                       TEXT,
    CONSTRAINT ck_mock_atendimento_idade
        CHECK (idade IS NULL OR idade BETWEEN 0 AND 120)
);

ALTER TABLE mock_pec_atendimentos
    ADD COLUMN IF NOT EXISTS turno_atendimento TEXT;

CREATE TABLE IF NOT EXISTS mock_populacao_negra_distrito (
    distrito_sanitario_codigo    TEXT PRIMARY KEY,
    populacao_negra_pct_esperado NUMERIC
        CHECK (
            populacao_negra_pct_esperado IS NULL
            OR populacao_negra_pct_esperado BETWEEN 0 AND 1
        )
);

COMMENT ON TABLE mock_pec_atendimentos IS
    'DADOS FICTICIOS/SIMULADOS. Nao representa pacientes ou atendimentos reais.';

COMMENT ON TABLE mock_populacao_negra_distrito IS
    'DADOS FICTICIOS/SIMULADOS. Referencia ilustrativa, nao representa '
    'a distribuicao real da populacao por distrito.';

CREATE INDEX IF NOT EXISTS idx_mock_atendimentos_data
    ON mock_pec_atendimentos (data_atendimento);

CREATE INDEX IF NOT EXISTS idx_mock_atendimentos_distrito
    ON mock_pec_atendimentos (distrito_sanitario_codigo);

CREATE INDEX IF NOT EXISTS idx_mock_atendimentos_equipe
    ON mock_pec_atendimentos (codigo_equipe);

COMMIT;

-- Exemplos de CRUD: a aplicacao envia os valores como parametros vinculados.
-- INSERT INTO mock_pec_atendimentos (
--     id_atendimento, codigo_equipe, cnes_unidade,
--     distrito_sanitario_codigo, data_atendimento, tipo_atendimento,
--     profissional_tipo, turno_atendimento, idade, raca_cor,
--     deficiencia_tipo, deseja_informar_orientacao_sexual,
--     orientacao_sexual, deseja_informar_identidade_genero,
--     identidade_genero, nome_social
-- ) VALUES (
--     :id_atendimento, :codigo_equipe, :cnes_unidade,
--     :distrito_sanitario_codigo, :data_atendimento, :tipo_atendimento,
--     :profissional_tipo, :turno_atendimento, :idade, :raca_cor,
--     :deficiencia_tipo, :deseja_informar_orientacao_sexual,
--     :orientacao_sexual, :deseja_informar_identidade_genero,
--     :identidade_genero, :nome_social
-- );
--
-- UPDATE mock_pec_atendimentos
-- SET raca_cor = :raca_cor, deficiencia_tipo = :deficiencia_tipo
-- WHERE id_atendimento = :id_atendimento;
--
-- DELETE FROM mock_pec_atendimentos
-- WHERE id_atendimento = :id_atendimento;
--
-- INSERT INTO mock_populacao_negra_distrito (
--     distrito_sanitario_codigo, populacao_negra_pct_esperado
-- ) VALUES (:distrito, :percentual);
--
-- UPDATE mock_populacao_negra_distrito
-- SET populacao_negra_pct_esperado = :percentual
-- WHERE distrito_sanitario_codigo = :distrito;
--
-- DELETE FROM mock_populacao_negra_distrito
-- WHERE distrito_sanitario_codigo = :distrito;

-- Consulta 1: atendimentos por distrito e raca/cor.
SELECT distrito_sanitario_codigo AS distrito,
       raca_cor,
       COUNT(*) AS atendimentos
FROM mock_pec_atendimentos
WHERE raca_cor IS NOT NULL
GROUP BY distrito_sanitario_codigo, raca_cor
ORDER BY distrito_sanitario_codigo, raca_cor;

-- Consulta 2: completude dos campos por mes.
SELECT TO_CHAR(DATE_TRUNC('month', data_atendimento), 'YYYY-MM') AS mes,
       ROUND(
           COUNT(raca_cor)::numeric / NULLIF(COUNT(*), 0) * 100,
           1
       ) AS raca_cor_pct,
       ROUND(
           COUNT(deficiencia_tipo)::numeric / NULLIF(COUNT(*), 0) * 100,
           1
       ) AS deficiencia_pct,
       ROUND(
           (COUNT(orientacao_sexual) FILTER (WHERE idade >= 10))::numeric
               / NULLIF(COUNT(*) FILTER (WHERE idade >= 10), 0) * 100,
           1
       ) AS orientacao_sexual_pct,
       ROUND(
           (COUNT(identidade_genero) FILTER (WHERE idade >= 10))::numeric
               / NULLIF(COUNT(*) FILTER (WHERE idade >= 10), 0) * 100,
           1
       ) AS identidade_genero_pct
FROM mock_pec_atendimentos
WHERE data_atendimento IS NOT NULL
GROUP BY DATE_TRUNC('month', data_atendimento)
ORDER BY DATE_TRUNC('month', data_atendimento);

-- Consulta 3: equipes, unidades e atendimentos (JOIN).
SELECT u.distrito_sanitario_codigo AS distrito,
       e.codigo_equipe,
       COALESCE(u.nome_fantasia, u.nome_empresarial) AS unidade,
       COUNT(a.id_atendimento) AS atendimentos
FROM equipes_saude e
JOIN unidades_saude u ON u.cnes = e.cnes_unidade
LEFT JOIN mock_pec_atendimentos a
    ON a.codigo_equipe = e.codigo_equipe
GROUP BY u.distrito_sanitario_codigo,
         e.codigo_equipe,
         u.nome_fantasia,
         u.nome_empresarial
ORDER BY atendimentos DESC, e.codigo_equipe
LIMIT 100;

-- Consulta 4: percentual de referencia versus registros observados (JOIN).
SELECT p.distrito_sanitario_codigo AS distrito,
       ROUND(p.populacao_negra_pct_esperado * 100, 1)
           AS percentual_esperado,
       ROUND(
           (COUNT(*) FILTER (
               WHERE a.raca_cor IN ('Preta', 'Parda')
           ))::numeric / NULLIF(COUNT(a.raca_cor), 0) * 100,
           1
       ) AS percentual_observado,
       ROUND(
           p.populacao_negra_pct_esperado * 100
               - (COUNT(*) FILTER (
                   WHERE a.raca_cor IN ('Preta', 'Parda')
               ))::numeric / NULLIF(COUNT(a.raca_cor), 0) * 100,
           1
       ) AS diferenca_pontos_percentuais
FROM mock_populacao_negra_distrito p
LEFT JOIN mock_pec_atendimentos a
    ON a.distrito_sanitario_codigo = p.distrito_sanitario_codigo
GROUP BY p.distrito_sanitario_codigo,
         p.populacao_negra_pct_esperado
ORDER BY p.distrito_sanitario_codigo;
