"""Gera um relatório PDF dos índices da Etapa 04 e seus usos verificados."""

import html
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARQUIVO_SAIDA = ROOT / "Indices_Etapa_04_EquiDados.pdf"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def bloco(codigo):
    return f'<pre><code>{html.escape(codigo.strip())}</code></pre>'


def criar_html():
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>EquiDados — Índices da Etapa 04</title>
<style>
  @page {{ size: A4 landscape; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: "Segoe UI", Arial, sans-serif;
      color: #262033; background: #f7f5fa; }}
  .page {{ width: 297mm; height: 210mm; padding: 10mm 12mm 12mm;
      position: relative; overflow: hidden; page-break-after: always; }}
  .page:last-child {{ page-break-after: auto; }}
  .top {{ display: flex; justify-content: space-between; align-items: flex-start;
      border-bottom: 1px solid #ded8e9; padding-bottom: 6px; margin-bottom: 10px; }}
  h1 {{ color: #42118f; font-size: 23px; margin: 0 0 3px; }}
  .subtitle {{ color: #706b7a; font-size: 10px; }}
  .badge {{ border-radius: 20px; padding: 7px 12px; background: #eee8f7;
      color: #42118f; font-weight: 700; font-size: 9px; white-space: nowrap; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  .card {{ background: white; border: 1px solid #ded8e9; border-radius: 9px;
      padding: 10px 12px; }}
  .card h2 {{ color: #42118f; font-size: 13px; margin: 0 0 7px; }}
  .index {{ color: #42118f; font: 700 11px Consolas, monospace; margin-bottom: 5px; }}
  .desc {{ color: #706b7a; font-size: 10px; line-height: 1.55; margin-bottom: 6px; }}
  pre {{ white-space: pre-wrap; overflow-wrap: anywhere; margin: 6px 0;
      padding: 8px 10px; background: #fbfaff; border: 1px solid #e6e0ed;
      border-radius: 6px; color: #242033; font: 10.5px/1.5 Consolas,
      "Courier New", monospace; }}
  .tag {{ display: inline-block; border-radius: 10px; background: #eff7f5;
      color: #167c70; padding: 3px 7px; font-size: 8.5px; font-weight: 700; }}
  .note {{ margin-top: 9px; padding: 8px 10px; border-left: 3px solid #7652a6;
      background: #f0edf5; color: #514963; font-size: 10px; line-height: 1.5; }}
  .map {{ display: grid; grid-template-columns: 190px 1fr; gap: 8px;
      padding: 8px 0; border-bottom: 1px solid #f0edf4; }}
  .map:last-child {{ border-bottom: 0; }}
  .map strong {{ color: #42118f; font: 700 9px Consolas, monospace; }}
  .map p {{ margin: 0; font-size: 9px; line-height: 1.5; }}
  .plan {{ margin-top: 8px; background: #211b2b; color: #e7e0f0;
      border-radius: 6px; padding: 8px 10px; font: 9.5px/1.45 Consolas,
      "Courier New", monospace; white-space: pre-wrap; }}
  .plan strong {{ color: #9de0c9; }}
  .footer {{ position: absolute; bottom: 5mm; left: 12mm; right: 12mm;
      border-top: 1px solid #ded8e9; padding-top: 4px; display: flex;
      justify-content: space-between; color: #706b7a; font-size: 7px; }}
</style></head><body>
<section class="page">
  <div class="top"><div><h1>EquiDados | Índices da Etapa 04</h1>
    <div class="subtitle">Definição, campos, justificativa e consultas beneficiadas</div></div>
    <div class="badge">POSTGRESQL · NEON · 08 NOV 2026</div></div>
  <div class="grid">
    <article class="card">
      <h2>Índice 1 — equipe + data</h2>
      <div class="index">idx_mock_atendimentos_equipe_data_etapa04</div>
      <div class="desc">Chave composta (codigo_equipe, data_atendimento). A equipe é
        comparada por igualdade; dentro de cada equipe, a consulta restringe o período
        por intervalo de datas. Essa ordem atende o JOIN e a janela temporal juntos.</div>
      {bloco("""CREATE INDEX IF NOT EXISTS idx_mock_atendimentos_equipe_data_etapa04
    ON mock_pec_atendimentos (codigo_equipe, data_atendimento);""")}
      <span class="tag">PREDICADO: EQUIPE = ? AND DATA BETWEEN ? AND ?</span>
    </article>
    <article class="card">
      <h2>Índice 2 — data + distrito</h2>
      <div class="index">idx_mock_atendimentos_data_distrito_etapa04</div>
      <div class="desc">Chave composta (data_atendimento, distrito_sanitario_codigo).
        A janela recente restringe primeiro a data; o índice também contém o distrito
        selecionado e agregado no resultado territorial.</div>
      {bloco("""CREATE INDEX IF NOT EXISTS idx_mock_atendimentos_data_distrito_etapa04
    ON mock_pec_atendimentos (data_atendimento, distrito_sanitario_codigo);""")}
      <span class="tag">PREDICADO: DATA BETWEEN ? AND ? · DISTRITO IS NOT NULL</span>
    </article>
  </div>
  <div class="note"><strong>Por que compostos?</strong> Os índices básicos da aplicação
    cobrem equipe, data e distrito isoladamente. Estes dois foram adicionados para
    os padrões conjuntos observados nas consultas: igualdade da equipe mais faixa de
    data e faixa de data mais leitura do distrito. A escolha de colunas e ordem segue
    esses predicados, não apenas a existência genérica dos campos.</div>
  <div class="note"><strong>Origem:</strong> definições presentes em
    <code>Etapa_04_Consultas_Avancadas.sql</code>. Os registros consultados são da
    tabela <code>mock_pec_atendimentos</code>, explicitamente identificada como
    fictícia/simulada no projeto.</div>
  <div class="footer"><span>EquiDados · Justificativa dos índices</span><span>01 / 02</span></div>
</section>
<section class="page">
  <div class="top"><div><h1>Uso nas consultas e planos EXPLAIN</h1>
    <div class="subtitle">Correspondência com filtros/joins e verificação no PostgreSQL/Neon</div></div>
    <div class="badge">PLANOS EXPLAIN SEM ANALYZE · SOMENTE LEITURA</div></div>
  <div class="grid">
    <article class="card">
      <h2>Índice 1 → Consulta 1: anti join</h2>
      <div class="desc">A junção por equipe e a faixa móvel de 90 dias aparecem no
        predicado do LEFT JOIN. O anti join seleciona as equipes sem correspondência.</div>
      {bloco("""LEFT JOIN mock_pec_atendimentos a
    ON a.codigo_equipe = e.codigo_equipe
   AND a.data_atendimento >= CURRENT_DATE - INTERVAL '90 days'
   AND a.data_atendimento <= CURRENT_DATE
WHERE a.id_atendimento IS NULL""")}
      <div class="plan"><strong>Bitmap Index Scan on idx_mock_atendimentos_equipe_data_etapa04</strong>
Index Cond: ((codigo_equipe = e.codigo_equipe)
  AND (data_atendimento >= CURRENT_DATE - '90 days')
  AND (data_atendimento <= CURRENT_DATE))</div>
    </article>
    <article class="card">
      <h2>Índice 2 → visão territorial e Consulta 2</h2>
      <div class="desc"><code>vw_equidade_distrital</code> agrega atendimentos dos
        últimos 90 dias por distrito. A CTE <code>atendimentos_por_distrito</code>
        da consulta FULL OUTER JOIN repete o mesmo filtro temporal/territorial.</div>
      {bloco("""WHERE data_atendimento >= CURRENT_DATE - INTERVAL '90 days'
  AND data_atendimento < CURRENT_DATE + INTERVAL '1 day'
  AND distrito_sanitario_codigo IS NOT NULL
GROUP BY distrito_sanitario_codigo""")}
      <div class="plan"><strong>Index Only Scan using idx_mock_atendimentos_data_distrito_etapa04</strong>
Index Cond: ((data_atendimento >= CURRENT_DATE - '90 days')
  AND (data_atendimento < CURRENT_DATE + '1 day')
  AND (distrito_sanitario_codigo IS NOT NULL))</div>
    </article>
  </div>
  <div class="note"><strong>Verificação:</strong> os planos foram obtidos com
    <code>EXPLAIN</code> no PostgreSQL/Neon configurado para o projeto. O plano do
    anti join selecionou <code>Bitmap Index Scan</code> pelo índice equipe/data; o
    agregado territorial selecionou <code>Index Only Scan</code> pelo índice
    data/distrito. <code>EXPLAIN</code> verifica a decisão do planejador, sem executar
    a consulta nem medir o tempo real.</div>
  <div class="note"><strong>Nota de execução:</strong> o PostgreSQL decide o plano
    conforme estatísticas, volume e parâmetros de cada banco. O mapeamento mostra
    que os índices correspondem diretamente aos predicados implementados; a seleção
    observada neste ambiente confirma o uso nas consultas representativas da Etapa 04.</div>
  <div class="footer"><span>Fonte dos predicados: Etapa_04_Consultas_Avancadas.sql</span><span>02 / 02</span></div>
</section></body></html>"""


def gerar_pdf():
    if not EDGE.is_file():
        raise FileNotFoundError(
            f"Microsoft Edge não encontrado para exportar o PDF: {EDGE}"
        )

    with tempfile.TemporaryDirectory(prefix="equidados-indices-etapa04-") as pasta:
        arquivo_html = Path(pasta) / "indices_etapa04.html"
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
