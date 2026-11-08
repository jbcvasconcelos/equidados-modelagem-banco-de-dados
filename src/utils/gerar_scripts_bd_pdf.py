"""Gera um PDF com os scripts atuais de criação e carga do banco EquiDados."""

import html
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARQUIVO_SAIDA = ROOT / "Scripts_Criacao_e_Insercao_BD_EquiDados.pdf"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def trecho_ate_commit(caminho):
    conteudo = caminho.read_text(encoding="utf-8")
    correspondencia = re.search(r"(?im)^COMMIT;\s*$", conteudo)
    if not correspondencia:
        raise ValueError(f"COMMIT não encontrado no script SQL: {caminho.name}")
    return conteudo[:correspondencia.end()]


def bloco_codigo(conteudo):
    linhas = conteudo.rstrip().splitlines()
    return "".join(
        '<div class="linha"><span class="numero">{:03d}</span>'
        '<code>{}</code></div>'.format(numero, html.escape(linha))
        for numero, linha in enumerate(linhas, start=1)
    )


def secao_codigo(titulo, descricao, caminho, conteudo, classe=""):
    return f"""
    <section class="secao {classe}">
      <header class="cabecalho-secao">
        <h2>{html.escape(titulo)}</h2>
        <span>{html.escape(descricao)}</span>
      </header>
      <div class="origem">Arquivo de origem: <code>{html.escape(str(caminho.relative_to(ROOT)))}</code></div>
      <div class="codigo">{bloco_codigo(conteudo)}</div>
    </section>
    """


def criar_html():
    sql_base = ROOT / "arquivo.sql"
    sql_etapa04 = ROOT / "Etapa_04_Consultas_Avancadas.sql"
    carga_reais = ROOT / "src" / "transform" / "mongo_para_neon.py"
    carga_simulados = ROOT / "src" / "transform" / "mongo_para_neon_mock.py"

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>EquiDados — Scripts de criação e inserção do banco</title>
<style>
  @page {{ size: A4 portrait; margin: 13mm 12mm 14mm; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; color: #262033; background: white;
      font-family: "Segoe UI", Arial, sans-serif; }}
  .capa {{ min-height: 255mm; page-break-after: always; padding: 18mm 12mm;
      background: #f7f5fa; border: 1px solid #e6e0ed; }}
  h1 {{ color: #42118f; font-size: 25px; margin: 0 0 8px; }}
  .subtitulo {{ color: #706b7a; font-size: 13px; margin-bottom: 22px; }}
  .selo {{ display: inline-block; background: #eee8f7; color: #42118f;
      padding: 7px 12px; border-radius: 20px; font-size: 10px; font-weight: 700; }}
  .capa h2 {{ color: #42118f; font-size: 15px; margin: 24px 0 8px; }}
  .capa p, .capa li {{ font-size: 11px; line-height: 1.65; }}
  .capa ul {{ padding-left: 18px; }}
  .aviso {{ margin-top: 20px; padding: 12px; border-left: 4px solid #7952a5;
      background: #f0edf5; font-size: 10px; line-height: 1.6; }}
  .secao {{ page-break-before: always; }}
  .cabecalho-secao {{ border-bottom: 2px solid #7652a6; padding-bottom: 7px;
      margin: 0 0 7px; }}
  .cabecalho-secao h2 {{ color: #42118f; font-size: 16px; margin: 0 0 3px; }}
  .cabecalho-secao span {{ color: #706b7a; font-size: 9px; }}
  .origem {{ color: #706b7a; font-size: 8px; margin: 0 0 8px; }}
  .origem code {{ font-family: Consolas, "Courier New", monospace; }}
  .nota {{ border-left: 3px solid #167c70; background: #eff7f5; padding: 8px 10px;
      font-size: 9px; line-height: 1.5; margin: 0 0 9px; }}
  .codigo {{ border: 1px solid #e2dcea; border-radius: 5px;
      background: #fbfaff; padding: 6px 5px; }}
  .linha {{ display: grid; grid-template-columns: 31px minmax(0, 1fr);
      column-gap: 5px; break-inside: avoid; min-height: 11px; }}
  .numero {{ text-align: right; color: #9a92a5; font: 7px/1.35 Consolas,
      "Courier New", monospace; user-select: none; }}
  .linha code {{ white-space: pre-wrap; overflow-wrap: anywhere;
      color: #242033; font: 9.5px/1.3 Consolas, "Courier New", monospace; }}
  .rodape {{ position: fixed; bottom: -9mm; left: 0; right: 0;
      padding-top: 3px; border-top: 1px solid #ded8e9; color: #706b7a;
      font-size: 7px; text-align: right; }}
</style></head><body>
<section class="capa">
  <span class="selo">POSTGRESQL · EQUiDADOS · VERSÃO ATUAL · 08 NOV 2026</span>
  <h1>Scripts de criação e inserção do banco</h1>
  <div class="subtitulo">DDL do banco e scripts de carga — reunidos em um único PDF</div>
  <h2>Conteúdo e ordem de execução</h2>
  <ol>
    <li><strong>Criação do esquema:</strong> tabelas, restrições e índices básicos
      do <code>arquivo.sql</code>.</li>
    <li><strong>Objetos da Etapa 04:</strong> dois índices avançados e duas visões,
      extraídos do script da etapa.</li>
    <li><strong>Inserção/carga:</strong> scripts Python que leem as coleções do
      MongoDB e inserem/atualizam os registros no PostgreSQL/Neon.</li>
  </ol>
  <h2>Como os dados são inseridos</h2>
  <p>As fontes reais de unidades, equipes e Censo são carregadas por
    <code>mongo_para_neon.py</code>. Os dados de atendimentos e a referência
    territorial fictícios/simulados são carregados por
    <code>mongo_para_neon_mock.py</code>. Os scripts criam as tabelas necessárias
    antes da carga e usam comandos parametrizados com <code>INSERT ... ON CONFLICT</code>
    para inserir ou atualizar pelas chaves primárias.</p>
  <div class="aviso"><strong>Configuração:</strong> a execução requer
    <code>MONGO_URI</code> e <code>NEON_DATABASE_URL</code> definidos no arquivo
    local <code>.env</code>. Credenciais não fazem parte deste documento.
    As tabelas com prefixo <code>mock_</code> contêm apenas dados
    fictícios/simulados; não representam pacientes nem atendimentos reais.</div>
  <h2>Arquivos-fonte incluídos</h2>
  <ul>
    <li><code>arquivo.sql</code> — DDL de criação (somente a seção de criação).</li>
    <li><code>Etapa_04_Consultas_Avancadas.sql</code> — índices e visões.</li>
    <li><code>src/transform/mongo_para_neon.py</code> — criação e carga das tabelas reais.</li>
    <li><code>src/transform/mongo_para_neon_mock.py</code> — criação e carga das tabelas simuladas.</li>
  </ul>
</section>
{secao_codigo(
    "01 | Criação do esquema base",
    "DDL PostgreSQL: tabelas, chaves, restrições, comentários e índices básicos.",
    sql_base,
    trecho_ate_commit(sql_base),
)}
{secao_codigo(
    "02 | Índices e visões da Etapa 04",
    "DDL da etapa avançada; as consultas SELECT do arquivo original não fazem parte deste recorte.",
    sql_etapa04,
    trecho_ate_commit(sql_etapa04),
)}
{secao_codigo(
    "03 | Inserção dos dados reais",
    "Script Python completo: MongoDB → PostgreSQL/Neon, tabelas CNES e Censo.",
    carga_reais,
    carga_reais.read_text(encoding="utf-8"),
    "carga",
)}
{secao_codigo(
    "04 | Inserção dos dados simulados",
    "Script Python completo: MongoDB → PostgreSQL/Neon, tabelas mock_.",
    carga_simulados,
    carga_simulados.read_text(encoding="utf-8"),
    "carga",
)}
<div class="rodape">EquiDados · Scripts de criação e inserção do banco</div>
</body></html>"""


def gerar_pdf():
    if not EDGE.is_file():
        raise FileNotFoundError(
            f"Microsoft Edge não encontrado para exportar o PDF: {EDGE}"
        )

    with tempfile.TemporaryDirectory(prefix="equidados-scripts-bd-") as pasta:
        arquivo_html = Path(pasta) / "scripts_bd.html"
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
