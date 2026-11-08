"""Gera PDF com as quatro consultas SQL avançadas da Etapa 04."""

import html
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FONTE_SQL = ROOT / "Etapa_04_Consultas_Avancadas.sql"
ARQUIVO_SAIDA = ROOT / "Consultas_Avancadas_Etapa_04_EquiDados.pdf"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

EXPLICACOES = {
    1: (
        "ANTI JOIN · LEFT JOIN + IS NULL",
        "Localiza equipes ativas que não têm atendimentos simulados associados "
        "nos últimos 90 dias. O LEFT JOIN mantém equipes sem correspondência; "
        "o filtro IS NULL seleciona somente essas equipes.",
        "Uma linha por equipe ativa sem atendimento no período, com unidade e distrito "
        "quando disponíveis.",
    ),
    2: (
        "FULL OUTER JOIN",
        "Compara os distritos presentes no cadastro de unidades com os que aparecem "
        "nos atendimentos recentes. O FULL OUTER JOIN preserva distritos existentes "
        "em apenas uma das fontes.",
        "Distrito, total de unidades, atendimentos recentes e indicação de quais fontes "
        "têm registros.",
    ),
    3: (
        "SUBCONSULTA ESCALAR · MÉDIA",
        "Conta os atendimentos por equipe e compara cada total com a média dos totais "
        "das equipes que têm registros. A subconsulta retorna um único valor: a média.",
        "Equipes acima da média, ordenadas por volume decrescente de atendimentos.",
    ),
    4: (
        "SUBCONSULTA ESCALAR · PROPORÇÃO",
        "Calcula a proporção de registros Preta/Parda por distrito e a compara com "
        "a proporção municipal observada no conjunto simulado, calculada pela "
        "subconsulta escalar.",
        "Distritos acima da proporção municipal observada, com contagens e percentual "
        "distrital. O percentual é baseado nos registros simulados.",
    ),
}


def extrair_consultas():
    fonte = FONTE_SQL.read_text(encoding="utf-8")
    marcadores = list(re.finditer(r"(?m)^-- CONSULTA ([1-4]) - (.+)$", fonte))
    if len(marcadores) != 4:
        raise ValueError(
            f"Esperadas 4 consultas marcadas em {FONTE_SQL.name}; "
            f"foram encontradas {len(marcadores)}."
        )

    consultas = []
    for indice, marcador in enumerate(marcadores):
        final = marcadores[indice + 1].start() if indice + 1 < len(marcadores) else len(fonte)
        numero = int(marcador.group(1))
        texto = fonte[marcador.start():final].strip()
        if not re.search(r"(?im)^SELECT\b|^WITH\b", texto):
            raise ValueError(f"A consulta {numero} não contém SELECT/WITH.")
        consultas.append((numero, texto))
    return consultas


def renderizar_consulta(numero, texto):
    titulo, explicacao, resultado = EXPLICACOES[numero]
    return f"""
    <section class="pagina consulta">
      <header class="top">
        <div><h1>Consulta {numero} | Etapa 04</h1>
          <div class="subtitle">{html.escape(titulo)}</div></div>
        <div class="badge">POSTGRESQL · EQUiDADOS</div>
      </header>
      <div class="descricao"><strong>Objetivo.</strong> {html.escape(explicacao)}</div>
      <div class="resultado"><strong>Resultado esperado.</strong> {html.escape(resultado)}</div>
      <div class="rotulo">SQL original de <code>Etapa_04_Consultas_Avancadas.sql</code></div>
      <pre><code>{html.escape(texto)}</code></pre>
      <footer><span>Dados de atendimento identificados como fictícios/simulados</span>
        <span>{numero} / 4</span></footer>
    </section>
    """


def criar_html():
    consultas = extrair_consultas()
    paginas = "".join(renderizar_consulta(numero, texto) for numero, texto in consultas)
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>EquiDados — Consultas avançadas — Etapa 04</title>
<style>
  @page {{ size: A4 portrait; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; color: #262033; background: #f7f5fa;
      font-family: "Segoe UI", Arial, sans-serif; }}
  .pagina {{ width: 210mm; height: 297mm; padding: 13mm 13mm 15mm;
      position: relative; overflow: hidden; page-break-after: always; }}
  .pagina:last-child {{ page-break-after: auto; }}
  .top {{ display: flex; justify-content: space-between; align-items: flex-start;
      border-bottom: 2px solid #7652a6; padding-bottom: 7px; margin-bottom: 10px; }}
  h1 {{ color: #42118f; font-size: 21px; margin: 0 0 3px; }}
  .subtitle {{ color: #706b7a; font-size: 11px; }}
  .badge {{ border-radius: 20px; padding: 7px 10px; background: #eee8f7;
      color: #42118f; font-weight: 700; font-size: 8px; white-space: nowrap; }}
  .descricao, .resultado {{ background: white; border: 1px solid #ded8e9;
      border-radius: 7px; padding: 8px 10px; margin-bottom: 7px;
      font-size: 9px; line-height: 1.5; }}
  .descricao strong, .resultado strong {{ color: #42118f; }}
  .rotulo {{ color: #706b7a; font-size: 8px; margin: 9px 0 5px; }}
  .rotulo code {{ font-family: Consolas, "Courier New", monospace; }}
  pre {{ margin: 0; padding: 9px 10px; border: 1px solid #e2dcea;
      border-radius: 7px; background: #fff; white-space: pre-wrap;
      overflow-wrap: anywhere; color: #242033;
      font: 8.6px/1.36 Consolas, "Courier New", monospace; }}
  footer {{ position: absolute; bottom: 6mm; left: 13mm; right: 13mm;
      border-top: 1px solid #ded8e9; padding-top: 4px; display: flex;
      justify-content: space-between; color: #706b7a; font-size: 7px; }}
</style></head><body>{paginas}</body></html>"""


def gerar_pdf():
    if not EDGE.is_file():
        raise FileNotFoundError(
            f"Microsoft Edge não encontrado para exportar o PDF: {EDGE}"
        )

    with tempfile.TemporaryDirectory(prefix="equidados-consultas-etapa04-") as pasta:
        arquivo_html = Path(pasta) / "consultas_etapa04.html"
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
