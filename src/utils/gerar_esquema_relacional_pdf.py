"""Gera o esquema relacional escrito atualizado do EquiDados em PDF."""

import html
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARQUIVO_SAIDA = ROOT / "Esquema_Relacional_EquiDados_Ultima_Versao.pdf"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def campo(nome, tipo, detalhe=""):
    sufixo = f'<span class="detalhe">{html.escape(detalhe)}</span>' if detalhe else ""
    return (
        f'<li><code>{html.escape(nome)}</code><span class="tipo">'
        f'{html.escape(tipo)}</span>{sufixo}</li>'
    )


def tabela(nome, descricao, campos, classe=""):
    return (
        f'<article class="card {classe}"><header><h2>{html.escape(nome)}</h2>'
        f'<span>{html.escape(descricao)}</span></header><ul>'
        f'{"".join(campos)}</ul></article>'
    )


def lista_campos(campos):
    return [campo(*item) for item in campos]


def criar_html():
    unidades = tabela(
        "unidades_saude",
        "Cadastro de estabelecimentos — fonte CNES",
        lista_campos([
            ("cnes", "TEXT", "PK"),
            ("nome_fantasia", "TEXT"),
            ("nome_empresarial", "TEXT"),
            ("bairro", "TEXT"),
            ("distrito_sanitario_codigo", "TEXT"),
            ("distrito_sanitario_nome", "TEXT"),
            ("endereco", "TEXT"),
            ("cep", "TEXT"),
            ("latitude", "DOUBLE PRECISION"),
            ("longitude", "DOUBLE PRECISION"),
            ("tipo_estabelecimento", "TEXT"),
        ]),
    )
    equipes = tabela(
        "equipes_saude",
        "Equipes vinculadas opcionalmente a uma unidade",
        lista_campos([
            ("codigo_equipe", "TEXT", "PK"),
            ("nome_equipe", "TEXT"),
            ("tipo_equipe", "TEXT"),
            ("cnes_unidade", "TEXT", "FK → unidades_saude(cnes)"),
            ("data_ativacao", "TEXT"),
            ("data_desativacao", "TEXT"),
        ]),
    )
    censo_raca = tabela(
        "censo_raca_cor",
        "População municipal por categoria — IBGE",
        lista_campos([
            ("raca_cor", "TEXT", "PK"),
            ("populacao", "BIGINT"),
            ("ano", "INTEGER"),
        ]),
    )
    censo_deficiencia = tabela(
        "censo_deficiencia",
        "População municipal por dificuldade — IBGE",
        lista_campos([
            ("tipo_dificuldade", "TEXT", "PK"),
            ("populacao", "BIGINT"),
            ("ano", "INTEGER"),
            ("e_total", "BOOLEAN", "NOT NULL DEFAULT FALSE"),
        ]),
    )
    atendimentos = tabela(
        "mock_pec_atendimentos",
        "Registros fictícios/simulados — não representam pacientes reais",
        lista_campos([
            ("id_atendimento", "INTEGER", "PK"),
            ("codigo_equipe", "TEXT", "FK → equipes_saude(codigo_equipe)"),
            ("cnes_unidade", "TEXT", "FK → unidades_saude(cnes)"),
            ("distrito_sanitario_codigo", "TEXT"),
            ("data_atendimento", "DATE"),
            ("tipo_atendimento", "TEXT"),
            ("profissional_tipo", "TEXT"),
            ("turno_atendimento", "TEXT"),
            ("idade", "INTEGER", "CHECK: NULL ou de 0 a 120"),
            ("raca_cor", "TEXT"),
            ("deficiencia_tipo", "TEXT"),
            ("deseja_informar_orientacao_sexual", "TEXT"),
            ("orientacao_sexual", "TEXT"),
            ("deseja_informar_identidade_genero", "TEXT"),
            ("identidade_genero", "TEXT"),
            ("nome_social", "TEXT"),
        ]),
        "simulado",
    )
    referencia = tabela(
        "mock_populacao_negra_distrito",
        "Referência distrital ilustrativa e simulada",
        lista_campos([
            ("distrito_sanitario_codigo", "TEXT", "PK"),
            (
                "populacao_negra_pct_esperado",
                "NUMERIC",
                "CHECK: NULL ou entre 0 e 1",
            ),
        ]),
        "simulado",
    )

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>EquiDados — Esquema Relacional — Última versão</title>
<style>
  @page {{ size: A4 landscape; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; font-family: "Segoe UI", Arial, sans-serif;
      color: #262033; background: #f7f5fa; }}
  .page {{ width: 297mm; height: 210mm; padding: 10mm 12mm 12mm;
      position: relative; overflow: hidden; page-break-after: always;
      background: #f7f5fa; }}
  .page:last-child {{ page-break-after: auto; }}
  .top {{ display: flex; justify-content: space-between; align-items: flex-start;
      border-bottom: 1px solid #ded8e9; padding-bottom: 6px; margin-bottom: 10px; }}
  h1 {{ color: #42118f; font-size: 23px; margin: 0 0 3px; }}
  .subtitle {{ color: #706b7a; font-size: 10px; }}
  .badge {{ border-radius: 20px; padding: 7px 12px; background: #eee8f7;
      color: #42118f; font-weight: 700; font-size: 9px; white-space: nowrap; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  .stack {{ display: flex; flex-direction: column; gap: 9px; }}
  .card {{ background: white; border: 1px solid #ded8e9; border-radius: 9px;
      overflow: hidden; break-inside: avoid; }}
  .card header {{ background: #42118f; color: white; padding: 7px 10px;
      display: flex; justify-content: space-between; align-items: center; gap: 6px; }}
  .card header h2 {{ margin: 0; font-size: 11px; }}
  .card header span {{ font-size: 8px; text-align: right; opacity: .9; }}
  .card.simulado header {{ background: #7952a5; }}
  ul {{ list-style: none; padding: 5px 10px 7px; margin: 0; }}
  li {{ display: grid; grid-template-columns: 1fr auto; column-gap: 8px;
      align-items: baseline; min-height: 18px; font-size: 9px;
      border-bottom: 1px solid #f0edf4; }}
  li:last-child {{ border-bottom: 0; }}
  code {{ font-family: Consolas, "Courier New", monospace; font-size: 8.6px; }}
  .tipo {{ color: #706b7a; text-align: right; white-space: nowrap; }}
  .detalhe {{ grid-column: 1 / -1; color: #167c70; font-size: 7px;
      margin: -1px 0 3px; }}
  .duas-colunas {{ display: grid; grid-template-columns: 1fr 1fr;
      column-gap: 12px; }}
  .note {{ background: #f0edf5; border-left: 3px solid #7652a6;
      padding: 8px 10px; font-size: 9px; line-height: 1.45; color: #514963; }}
  .note strong {{ color: #42118f; }}
  .plain {{ background: white; border: 1px solid #ded8e9; border-radius: 9px;
      padding: 9px 11px; font-size: 9px; line-height: 1.5; }}
  .plain h2 {{ font-size: 10px; color: #42118f; margin: 0 0 5px; }}
  .plain p {{ margin: 3px 0; }}
  .plain code {{ font-size: 8.2px; }}
  .view-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
  .view-box {{ background: #f8f6fb; border: 1px solid #e6e0ed;
      border-radius: 7px; padding: 7px; }}
  .view-box h3 {{ color: #42118f; font: 700 9px Consolas, monospace;
      margin: 0 0 5px; }}
  .view-box p {{ margin: 0; font-size: 8px; line-height: 1.5; }}
  .footer {{ position: absolute; bottom: 5mm; left: 12mm; right: 12mm;
      border-top: 1px solid #ded8e9; padding-top: 4px; display: flex;
      justify-content: space-between; color: #706b7a; font-size: 7px; }}
</style></head><body>
<section class="page">
  <div class="top"><div><h1>EquiDados | Esquema Relacional</h1>
    <div class="subtitle">Versão atualizada — relações, atributos, domínios e chaves</div></div>
    <div class="badge">POSTGRESQL · ETAPA 04 · 08 NOV 2026</div></div>
  <div class="grid">
    <div class="stack">{unidades}{equipes}</div>
    <div class="stack">{censo_raca}{censo_deficiencia}
      <div class="note"><strong>Convenções:</strong> PK = chave primária; FK = chave estrangeira.
        Tipos são os declarados no DDL PostgreSQL. Colunas são opcionais (NULL) por padrão,
        exceto quando explicitamente indicado; toda PK é NOT NULL.</div></div>
  </div>
  <div class="footer"><span>EquiDados · CESAR School</span><span>01 / 03</span></div>
</section>
<section class="page">
  <div class="top"><div><h1>Relações operacionais e integridade</h1>
    <div class="subtitle">Tabelas de atendimentos e referência simulada, com suas restrições</div></div>
    <div class="badge">DADOS FICTÍCIOS/SIMULADOS IDENTIFICADOS</div></div>
  <div class="grid">
    <div class="stack">{atendimentos}</div>
    <div class="stack">{referencia}
      <div class="plain"><h2>Relacionamentos declarados no DDL</h2>
        <p><code>equipes_saude.cnes_unidade</code> → <code>unidades_saude.cnes</code></p>
        <p><code>mock_pec_atendimentos.codigo_equipe</code> → <code>equipes_saude.codigo_equipe</code></p>
        <p><code>mock_pec_atendimentos.cnes_unidade</code> → <code>unidades_saude.cnes</code></p>
        <p>As três FKs aceitam NULL e não declaram ações <code>ON DELETE</code> ou
        <code>ON UPDATE</code> personalizadas.</p></div>
      <div class="note"><strong>Integridade:</strong> idade deve ser NULL ou estar entre
        0 e 120. O percentual de referência deve ser NULL ou estar entre 0 e 1
        (fração, equivalente a 0%–100%). <code>censo_deficiencia.e_total</code>
        é NOT NULL e usa FALSE como padrão.</div>
      <div class="note"><strong>Limites do modelo físico:</strong> não há tabela própria
        de distritos nem FKs para distrito, raça/cor ou deficiência nos registros simulados.
        As tabelas de Censo são referências municipais independentes; não há ligação
        declarada entre elas e atendimentos.</div>
    </div>
  </div>
  <div class="footer"><span>As relações representam o DDL atual em arquivo.sql</span><span>02 / 03</span></div>
</section>
<section class="page">
  <div class="top"><div><h1>Visões e índices | Etapa 04</h1>
    <div class="subtitle">Objetos derivados e suporte às consultas analíticas</div></div>
    <div class="badge">OBJETOS DERIVADOS NÃO SÃO TABELAS-BASE</div></div>
  <div class="grid">
    <div class="stack">
      <div class="plain"><h2>vw_equidade_distrital</h2>
        <p>Consolida estrutura de unidades e equipes, atendimentos simulados e indicadores
        territoriais de completude/equidade. Agrega as fontes antes dos JOINs e combina
        os conjuntos por distrito com cinco LEFT JOINs.</p>
        <div class="view-grid">
          <div class="view-box"><h3>Identificação e volume</h3><p>
            distrito_sanitario_codigo · total_unidades · total_equipes ·
            total_atendimentos_simulados · atendimentos_ultimos_90_dias ·
            atendimentos_com_10_anos_ou_mais</p></div>
          <div class="view-box"><h3>Indicadores</h3><p>
            registros_com_raca_cor · completude_raca_cor_pct ·
            percentual_preto_ou_pardo_observado ·
            percentual_preto_ou_pardo_referencia_simulada ·
            diferenca_referencia_observado_pontos_percentuais</p></div>
        </div>
      </div>
      <div class="plain"><h2>vw_completude_por_equipe</h2>
        <p>Apresenta volume e completude agregados por equipe, com contexto da unidade e
        referência territorial. Apoia priorização gerencial; não avalia individualmente
        profissionais. Combina equipe, unidade e dados agregados com LEFT JOINs.</p>
        <div class="view-grid">
          <div class="view-box"><h3>Equipe e contexto</h3><p>
            codigo_equipe · nome_equipe · tipo_equipe · cnes_unidade · unidade ·
            distrito_sanitario_codigo · total_atendimentos_simulados ·
            data_ultimo_atendimento</p></div>
          <div class="view-box"><h3>Completude e referência</h3><p>
            completude_raca_cor_pct · completude_deficiencia_pct ·
            completude_orientacao_sexual_10_mais_pct ·
            completude_identidade_genero_10_mais_pct ·
            percentual_negro_referencia_distrital_simulada</p></div>
        </div>
      </div>
    </div>
    <div class="stack">
      <div class="plain"><h2>Índices explícitos</h2>
        <p><code>idx_mock_atendimentos_data</code> — (data_atendimento)</p>
        <p><code>idx_mock_atendimentos_distrito</code> — (distrito_sanitario_codigo)</p>
        <p><code>idx_mock_atendimentos_equipe</code> — (codigo_equipe)</p>
        <p><code>idx_mock_atendimentos_equipe_data_etapa04</code> —
          (codigo_equipe, data_atendimento)</p>
        <p><code>idx_mock_atendimentos_data_distrito_etapa04</code> —
          (data_atendimento, distrito_sanitario_codigo)</p>
        <p>O PostgreSQL também cria índices associados às chaves primárias.</p>
      </div>
      <div class="plain"><h2>Relacionamentos e cardinalidade</h2>
        <p><code>unidades_saude</code> 1:N <code>equipes_saude</code> pela FK
        <code>cnes_unidade</code>.</p>
        <p><code>equipes_saude</code> 1:N <code>mock_pec_atendimentos</code> pela FK
        <code>codigo_equipe</code>.</p>
        <p><code>unidades_saude</code> 1:N <code>mock_pec_atendimentos</code> pela FK
        <code>cnes_unidade</code>.</p>
        <p>Como as FKs aceitam NULL, os vínculos do lado do registro filho são opcionais.</p>
      </div>
      <div class="note"><strong>Semântica:</strong> os registros em tabelas
        <code>mock_</code> são fictícios/simulados. A referência por distrito é ilustrativa,
        não uma estatística oficial. O Censo IBGE disponível no modelo é municipal.</div>
      <div class="note"><strong>Fonte do esquema:</strong> DDL de
        <code>arquivo.sql</code> e visões/índices de
        <code>Etapa_04_Consultas_Avancadas.sql</code>.</div>
    </div>
  </div>
  <div class="footer"><span>EquiDados · Esquema relacional escrito atualizado</span><span>03 / 03</span></div>
</section></body></html>"""


def gerar_pdf():
    if not EDGE.is_file():
        raise FileNotFoundError(
            f"Microsoft Edge não encontrado para exportar o PDF: {EDGE}"
        )

    with tempfile.TemporaryDirectory(prefix="equidados-esquema-relacional-") as pasta:
        arquivo_html = Path(pasta) / "esquema_relacional.html"
        arquivo_html.write_text(criar_html(), encoding="utf-8")
        subprocess.run(
            [
                str(EDGE),
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={Path(pasta) / 'edge-profile'}",
                f"--print-to-pdf={ARQUIVO_SAIDA}",
                "--no-pdf-header-footer",
                arquivo_html.as_uri(),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

    if not ARQUIVO_SAIDA.is_file() or ARQUIVO_SAIDA.stat().st_size < 5000:
        raise RuntimeError("O PDF não foi gerado corretamente.")

    print(f"PDF gerado: {ARQUIVO_SAIDA}")
    print(f"Tamanho: {ARQUIVO_SAIDA.stat().st_size:,} bytes")


if __name__ == "__main__":
    gerar_pdf()
