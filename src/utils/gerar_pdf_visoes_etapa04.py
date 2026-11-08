"""Gera PDF com as duas visões analíticas e suas justificativas semânticas."""

import html
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FONTE_SQL = ROOT / "Etapa_04_Consultas_Avancadas.sql"
ARQUIVO_SAIDA = ROOT / "Visoes_Analiticas_Etapa_04_EquiDados.pdf"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

VISOES = {
    "vw_equidade_distrital": {
        "numero": 1,
        "titulo": "Equidade e estrutura por distrito",
        "subtitulo": "Consolida capacidade territorial, atendimentos e indicadores de equidade",
        "justificativa": (
            "A visão apoia a gestão da Atenção Básica ao reunir, por distrito sanitário, "
            "a quantidade de unidades e equipes, o volume de atendimentos simulados, "
            "a completude de raça/cor e a comparação ilustrativa entre registros "
            "Pretos/Pardos e uma referência territorial. Ajuda a identificar territórios "
            "que merecem investigação ou planejamento, sem tratar a referência simulada "
            "como estatística oficial."
        ),
        "joins": [
            "distritos → unidades (LEFT JOIN por distrito)",
            "distritos → equipes agregadas (LEFT JOIN por distrito)",
            "distritos → atendimentos agregados (LEFT JOIN por distrito)",
            "distritos → atendimentos dos últimos 90 dias (LEFT JOIN por distrito)",
            "distritos → referência negra simulada (LEFT JOIN por distrito)",
            "Dentro da CTE equipes: equipes_saude JOIN unidades_saude por CNES.",
        ],
        "resultados": (
            "Uma linha por código de distrito identificado nas unidades, nos atendimentos "
            "ou na referência simulada. Expõe totais de unidades/equipes/atendimentos, "
            "atendimentos recentes, completude de raça/cor, proporção observada "
            "Preta/Parda, referência simulada e diferença em pontos percentuais."
        ),
        "nota": (
            "Os agregados são calculados antes das junções para evitar multiplicar "
            "contagens ao combinar unidades, equipes e atendimentos. A referência por "
            "distrito e os atendimentos são simulados; não representam população ou "
            "atendimentos reais."
        ),
    },
    "vw_completude_por_equipe": {
        "numero": 2,
        "titulo": "Completude e volume por equipe",
        "subtitulo": "Contextualiza indicadores de preenchimento com unidade e território",
        "justificativa": (
            "Permite que equipes de gestão identifiquem necessidades de apoio e "
            "capacitação a partir do volume e da completude agregada dos registros de "
            "raça/cor, deficiência, orientação sexual e identidade de gênero. A unidade "
            "e o distrito dão contexto territorial para organizar ações; os percentuais "
            "não devem ser usados para classificar ou avaliar individualmente "
            "profissionais."
        ),
        "joins": [
            "equipes_saude → unidades_saude (LEFT JOIN por CNES)",
            "equipes_saude → atendimentos agregados (LEFT JOIN por código da equipe)",
            "unidade/distrito → referência negra simulada (LEFT JOIN por código do distrito)",
        ],
        "resultados": (
            "Uma linha por equipe cadastrada. Apresenta identificação da equipe, unidade "
            "e distrito, quantidade e data do último atendimento, percentuais de "
            "completude e referência territorial simulada."
        ),
        "nota": (
            "A CTE agrega os atendimentos por equipe antes dos JOINs. Os indicadores de "
            "orientação sexual e identidade de gênero usam como denominador somente os "
            "atendimentos com idade igual ou superior a 10 anos. Os registros e a "
            "referência distrital são fictícios/simulados."
        ),
    },
}


def extrair_sql_visao(nome):
    fonte = FONTE_SQL.read_text(encoding="utf-8")
    inicio = re.search(
        rf"(?im)^CREATE OR REPLACE VIEW {re.escape(nome)} AS\s*$",
        fonte,
    )
    if not inicio:
        raise ValueError(f"Definição SQL não encontrada para a visão {nome}.")
    fim = re.search(r"(?m)^COMMENT ON VIEW ", fonte[inicio.end():])
    if not fim:
        raise ValueError(f"Fim da definição SQL não encontrado para a visão {nome}.")
    definicao = fonte[inicio.start():inicio.end() + fim.start()].rstrip()
    if not definicao.endswith(";"):
        raise ValueError(f"Definição SQL incompleta para a visão {nome}.")
    return definicao


def renderizar_visao(nome, dados):
    sql = html.escape(extrair_sql_visao(nome))
    itens_joins = "".join(f"<li>{html.escape(item)}</li>" for item in dados["joins"])
    return f"""
    <section class="page">
      <header class="top">
        <div><h1>Visão {dados["numero"]} | {html.escape(dados["titulo"])}</h1>
          <div class="subtitle">{html.escape(nome)} · {html.escape(dados["subtitulo"])}</div></div>
        <div class="badge">POSTGRESQL · ETAPA 04</div>
      </header>
      <div class="grid">
        <div>
          <article class="card">
            <h2>Justificativa semântica no domínio</h2>
            <p>{html.escape(dados["justificativa"])}</p>
          </article>
          <article class="card">
            <h2>Junções e relacionamentos</h2>
            <p>As relações são combinadas pela chave territorial ou identificador
              correspondente. O uso de LEFT JOIN preserva as entidades de referência
              mesmo quando não há registro relacionado.</p>
            <ul>{itens_joins}</ul>
          </article>
          <article class="card">
            <h2>Granularidade e conteúdo</h2>
            <p>{html.escape(dados["resultados"])}</p>
          </article>
          <article class="note"><strong>Interpretação e limites:</strong>
            {html.escape(dados["nota"])}</article>
        </div>
        <div class="sql">
          <div class="sql-title">Definição SQL da visão — transcrita do script da Etapa 04</div>
          <pre><code>{sql}</code></pre>
        </div>
      </div>
      <footer><span>Fonte: Etapa_04_Consultas_Avancadas.sql</span>
        <span>{dados["numero"]} / 2</span></footer>
    </section>
    """


def criar_html():
    paginas = "".join(
        renderizar_visao(nome, dados) for nome, dados in VISOES.items()
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>EquiDados — Visões analíticas — Etapa 04</title>
<style>
  @page {{ size: A3 landscape; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; color: #262033; background: #f7f5fa;
      font-family: "Segoe UI", Arial, sans-serif; }}
  .page {{ width: 420mm; height: 297mm; padding: 10mm 12mm 13mm;
      position: relative; overflow: hidden; page-break-after: always; }}
  .page:last-child {{ page-break-after: auto; }}
  .top {{ display: flex; justify-content: space-between; align-items: flex-start;
      border-bottom: 2px solid #7652a6; padding-bottom: 7px; margin-bottom: 10px; }}
  h1 {{ color: #42118f; font-size: 23px; margin: 0 0 3px; }}
  .subtitle {{ color: #706b7a; font-size: 11px; }}
  .badge {{ border-radius: 20px; padding: 7px 10px; background: #eee8f7;
      color: #42118f; font-weight: 700; font-size: 9px; white-space: nowrap; }}
  .grid {{ display: grid; grid-template-columns: 0.85fr 1.15fr; gap: 10px;
      height: calc(100% - 58px); }}
  .grid > div:first-child {{ display: flex; flex-direction: column; gap: 8px; }}
  .card {{ background: white; border: 1px solid #ded8e9; border-radius: 8px;
      padding: 9px 11px; }}
  .card h2 {{ color: #42118f; font-size: 12px; margin: 0 0 5px; }}
  .card p, .card li {{ font-size: 9.5px; line-height: 1.45; }}
  .card p {{ margin: 0; }}
  .card ul {{ padding-left: 17px; margin: 5px 0 0; }}
  .card li {{ margin: 2px 0; }}
  .note {{ background: #f0edf5; border-left: 3px solid #7652a6;
      padding: 9px 11px; color: #514963; font-size: 9.5px; line-height: 1.5; }}
  .note strong {{ color: #42118f; }}
  .sql {{ min-height: 0; display: flex; flex-direction: column; }}
  .sql-title {{ color: #706b7a; font-size: 8px; margin: 0 0 5px; }}
  pre {{ flex: 1; min-height: 0; margin: 0; padding: 8px 9px;
      background: white; border: 1px solid #e2dcea; border-radius: 7px;
      overflow: hidden; white-space: pre-wrap; overflow-wrap: anywhere;
      color: #242033; font: 8px/1.16 Consolas, "Courier New", monospace; }}
  footer {{ position: absolute; bottom: 5mm; left: 12mm; right: 12mm;
      border-top: 1px solid #ded8e9; padding-top: 4px; display: flex;
      justify-content: space-between; color: #706b7a; font-size: 7px; }}
</style></head><body>{paginas}</body></html>"""


def gerar_pdf():
    if not EDGE.is_file():
        raise FileNotFoundError(
            f"Microsoft Edge não encontrado para exportar o PDF: {EDGE}"
        )

    with tempfile.TemporaryDirectory(prefix="equidados-visoes-etapa04-") as pasta:
        arquivo_html = Path(pasta) / "visoes_etapa04.html"
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
