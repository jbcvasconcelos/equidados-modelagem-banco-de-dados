"""Gera o modelo conceitual EquiDados atualizado em PDF A3 paisagem."""

import html
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARQUIVO_SAIDA = ROOT / "Modelo_Conceitual_EquiDados_Ultima_Versao.pdf"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

LARGURA = 1600
ALTURA = 1131
ROXO = "#42118f"
TEXTO = "#262033"
SECUNDARIO = "#706b7a"
LINHA = "#7652a6"
VERDE = "#167c70"


def criar_svg():
    partes = [
        f"""<svg xmlns="http://www.w3.org/2000/svg"
        width="420mm" height="297mm"
        viewBox="0 0 {LARGURA} {ALTURA}">
        <defs>
          <filter id="sombra" x="-15%" y="-15%" width="130%" height="140%">
            <feDropShadow dx="0" dy="5" stdDeviation="7"
                flood-color="#31136b" flood-opacity=".12"/>
          </filter>
          <marker id="seta" viewBox="0 0 10 10" refX="8" refY="5"
              markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0 0L10 5L0 10z" fill="{LINHA}"/>
          </marker>
          <style>
            text {{ font-family: "Segoe UI", Arial, sans-serif; fill: {TEXTO}; }}
            .titulo {{ font-size: 37px; font-weight: 750; fill: {ROXO}; }}
            .subtitulo {{ font-size: 18px; fill: {SECUNDARIO}; }}
            .cartao {{ fill: #fff; stroke: #ded8e9; stroke-width: 2;
                filter: url(#sombra); }}
            .conceitual {{ fill: #fff; stroke: {ROXO}; stroke-width: 2.5;
                stroke-dasharray: 9 7; filter: url(#sombra); }}
            .cabecalho {{ fill: {ROXO}; }}
            .simulado {{ fill: #7952a5; }}
            .fonte {{ fill: {VERDE}; }}
            .derivado {{ fill: #5e4d7b; }}
            .entidade {{ font-weight: 720; fill: #fff; }}
            .etiqueta {{ font-size: 12px; font-weight: 700; fill: #fff; }}
            .atributo {{ font-size: 15px; }}
            .atributo-pequeno {{ font-size: 13px; }}
            .relacao {{ fill: none; stroke: {LINHA}; stroke-width: 3;
                marker-end: url(#seta); stroke-linecap: round;
                stroke-linejoin: round; }}
            .relacao-opcional {{ fill: none; stroke: {LINHA}; stroke-width: 3;
                stroke-dasharray: 9 7; marker-end: url(#seta);
                stroke-linecap: round; stroke-linejoin: round; }}
            .relacao-derivada {{ fill: none; stroke: #927cae; stroke-width: 2.5;
                stroke-dasharray: 5 7; }}
            .pildora {{ fill: #fff; stroke: #e2dcea; stroke-width: 1.2; }}
            .cardinalidade {{ font-size: 12px; font-weight: 750; fill: {ROXO}; }}
            .nota {{ font-size: 14px; fill: {SECUNDARIO}; }}
            .relacao-texto {{ font-size: 14px; font-weight: 700; fill: {ROXO}; }}
            .secao {{ font-size: 15px; font-weight: 750; fill: {ROXO};
                letter-spacing: .5px; }}
          </style>
        </defs>
        <rect width="1600" height="1131" fill="#f7f5fa"/>
        <rect width="1600" height="150" fill="#fff"/>
        <rect x="50" y="43" width="8" height="58" rx="4" fill="{ROXO}"/>
        <text x="78" y="75" class="titulo">
            EquiDados | Modelo Conceitual
        </text>
        <text x="78" y="111" class="subtitulo">
            Versão atualizada — Equidade em Saúde no Recife |
            Modelo de domínio e relacionamentos
        </text>
        <rect x="1300" y="48" width="250" height="42" rx="21"
            fill="#eee8f7"/>
        <text x="1425" y="75" text-anchor="middle"
            style="font-size:15px;font-weight:700;fill:{ROXO}">
            ETAPA 04 · 08 NOV 2026
        </text>
        """
    ]

    def adicionar_caminho(dados, classe="relacao"):
        partes.append(f'<path d="{dados}" class="{classe}"/>')

    def adicionar_cardinalidade(x, y, rotulo, largura=None):
        largura = largura or max(40, len(rotulo) * 7.3 + 18)
        partes.append(
            f'<rect x="{x-largura/2}" y="{y-13}" width="{largura}" '
            'height="25" rx="12" class="pildora"/>'
        )
        partes.append(
            f'<text x="{x}" y="{y+4}" text-anchor="middle" '
            f'class="cardinalidade">{html.escape(rotulo)}</text>'
        )

    # Relacionamentos conceituais. As entidades são desenhadas por cima.
    adicionar_caminho("M378 435H418V274H457")
    adicionar_cardinalidade(391, 418, "1")
    adicionar_cardinalidade(437, 250, "0..N")
    partes.append(
        '<text x="412" y="355" text-anchor="middle" class="relacao-texto" '
        'transform="rotate(-90 412 355)">abrange</text>'
    )

    adicionar_caminho("M848 267H907")
    adicionar_cardinalidade(860, 239, "1")
    adicionar_cardinalidade(896, 279, "0..N")
    partes.append(
        '<text x="878" y="315" text-anchor="middle" '
        'class="relacao-texto">vincula</text>'
    )

    adicionar_caminho("M378 549H423V791H457")
    adicionar_cardinalidade(391, 530, "1")
    adicionar_cardinalidade(440, 814, "0..N")
    partes.append(
        '<text x="423" y="674" text-anchor="middle" class="relacao-texto" '
        'transform="rotate(90 423 674)">localiza</text>'
    )

    adicionar_caminho("M215 626V722")
    adicionar_cardinalidade(243, 648, "1")
    adicionar_cardinalidade(243, 699, "0..1")
    partes.append(
        '<text x="277" y="679" text-anchor="middle" '
        'class="relacao-texto">referência</text>'
    )

    adicionar_caminho("M765 398V518H883V632", "relacao-opcional")
    adicionar_cardinalidade(790, 418, "1")
    adicionar_cardinalidade(858, 614, "0..N")
    partes.append(
        '<text x="818" y="507" text-anchor="middle" '
        'class="relacao-texto">registra</text>'
    )

    adicionar_caminho("M1088 373V555H943V632", "relacao-opcional")
    adicionar_cardinalidade(1111, 396, "1")
    adicionar_cardinalidade(966, 614, "0..N")
    partes.append(
        '<text x="1016" y="543" text-anchor="middle" '
        'class="relacao-texto">vincula</text>'
    )

    def adicionar_entidade(
        x, y, largura, altura, titulo, atributos, tipo="normal",
        etiqueta="", pequeno=False,
    ):
        classes_cabecalho = {
            "normal": "cabecalho",
            "simulado": "simulado",
            "fonte": "fonte",
            "conceitual": "cabecalho",
        }
        classe_caixa = "conceitual" if tipo == "conceitual" else "cartao"
        classe_cabecalho = classes_cabecalho[tipo]
        partes.append(
            f'<g><rect x="{x}" y="{y}" width="{largura}" height="{altura}" '
            f'rx="17" class="{classe_caixa}"/>'
        )
        partes.append(
            f'<path d="M{x+17},{y}H{x+largura-17}Q{x+largura},{y} '
            f'{x+largura},{y+17}V{y+51}H{x}V{y+17}Q{x},{y} {x+17},{y}Z" '
            f'class="{classe_cabecalho}"/>'
        )
        tamanho_etiqueta = max(55, len(etiqueta) * 7 + 19) if etiqueta else 0
        espaco_titulo = largura - 40 - (
            tamanho_etiqueta + 12 if etiqueta else 0
        )
        tamanho_titulo = min(
            19,
            max(12, espaco_titulo / max(1, len(titulo) * 0.56)),
        )
        partes.append(
            f'<text x="{x+19}" y="{y+33}" class="entidade" '
            f'style="font-size:{tamanho_titulo:.1f}px">'
            f'{html.escape(titulo)}</text>'
        )
        if etiqueta:
            partes.append(
                f'<rect x="{x+largura-tamanho_etiqueta-10}" y="{y+13}" '
                f'width="{tamanho_etiqueta}" height="25" rx="12" '
                'fill="#fff" fill-opacity=".18"/>'
            )
            partes.append(
                f'<text x="{x+largura-tamanho_etiqueta/2-10}" y="{y+30}" '
                f'text-anchor="middle" class="etiqueta">'
                f'{html.escape(etiqueta)}</text>'
            )
        classe_atributo = "atributo-pequeno" if pequeno else "atributo"
        passo = 21 if pequeno else 24
        posicao_y = y + 78
        cor_ponto = VERDE if tipo == "fonte" else ROXO
        for atributo in atributos:
            partes.append(
                f'<circle cx="{x+24}" cy="{posicao_y-5}" r="3" '
                f'fill="{cor_ponto}"/>'
            )
            partes.append(
                f'<text x="{x+37}" y="{posicao_y}" '
                f'class="{classe_atributo}">{html.escape(atributo)}</text>'
            )
            posicao_y += passo
        partes.append("</g>")

    adicionar_entidade(
        48, 390, 330, 236, "DISTRITO SANITÁRIO",
        [
            "código (identificador conceitual)",
            "nome do distrito",
            "limite geográfico (Dados Recife)",
            "dimensão territorial compartilhada",
        ],
        "conceitual", "CONCEITUAL", True,
    )
    adicionar_entidade(
        48, 722, 330, 190, "REFERÊNCIA NEGRA POR DISTRITO",
        [
            "código do distrito",
            "percentual esperado de população negra",
            "referência ilustrativa e simulada",
        ],
        "simulado", "", True,
    )
    adicionar_entidade(
        465, 165, 383, 233, "UNIDADE DE SAÚDE",
        [
            "CNES (identificador)",
            "nome fantasia e nome empresarial",
            "tipo de estabelecimento",
            "endereço, bairro e CEP",
            "latitude e longitude",
            "código e nome do distrito",
        ],
        "normal", "CNES",
    )
    adicionar_entidade(
        907, 165, 358, 208, "EQUIPE DE SAÚDE",
        [
            "código da equipe (identificador)",
            "nome e tipo da equipe",
            "data de ativação e desativação",
            "CNES da unidade vinculada (opcional)",
        ],
        "normal", "CNES",
    )
    adicionar_entidade(
        465, 640, 500, 326, "ATENDIMENTO",
        [
            "identificador e data do atendimento",
            "tipo, profissional e turno",
            "idade e distrito sanitário",
            "raça/cor e tipo de deficiência",
            "consentimento e orientação sexual",
            "consentimento e identidade de gênero",
            "nome social",
        ],
        "simulado", "DADOS SIMULADOS",
    )
    adicionar_entidade(
        1300, 165, 255, 190, "CENSO DE RAÇA/COR",
        ["categoria de raça/cor", "população e ano", "fonte: IBGE"],
        "fonte", "IBGE", True,
    )
    adicionar_entidade(
        1300, 390, 255, 220, "CENSO DE DEFICIÊNCIA",
        [
            "tipo de dificuldade ou total",
            "população e ano",
            "indicador de total oficial",
            "fonte: IBGE",
        ],
        "fonte", "IBGE", True,
    )

    partes.append(
        '<rect x="1020" y="640" width="535" height="326" rx="17" '
        'fill="#f1edf6" stroke="#b9aacb" stroke-width="2" '
        'stroke-dasharray="8 7"/>'
        '<text x="1045" y="678" class="secao">'
        "VISÕES ANALÍTICAS DERIVADAS · ETAPA 04</text>"
        '<text x="1045" y="705" class="nota">'
        "Não são entidades-base; agregam dados para consulta da gestão."
        "</text>"
        '<rect x="1040" y="727" width="495" height="88" rx="12" '
        'fill="#fff" stroke="#ddd5e8"/>'
        f'<text x="1058" y="757" style="font-size:16px;font-weight:700;'
        f'fill:{ROXO}">vw_equidade_distrital</text>'
        '<text x="1058" y="783" class="atributo-pequeno">'
        "Unidades, equipes, atendimentos, completude</text>"
        '<text x="1058" y="803" class="atributo-pequeno">'
        "e referência territorial simulada por distrito.</text>"
        '<rect x="1040" y="828" width="495" height="92" rx="12" '
        'fill="#fff" stroke="#ddd5e8"/>'
        f'<text x="1058" y="858" style="font-size:16px;font-weight:700;'
        f'fill:{ROXO}">vw_completude_por_equipe</text>'
        '<text x="1058" y="884" class="atributo-pequeno">'
        "Completude agregada por equipe e unidade, com</text>"
        '<text x="1058" y="904" class="atributo-pequeno">'
        "referência distrital; não avalia profissionais.</text>"
    )
    adicionar_caminho("M965 802H1010", "relacao-derivada")
    adicionar_cardinalidade(988, 780, "derivação", 82)

    partes.append(
        '<line x1="48" y1="1000" x2="1555" y2="1000" '
        'stroke="#e1dce9" stroke-width="2"/>'
        '<text x="50" y="1032" class="secao">LEITURA DO MODELO</text>'
        '<text x="50" y="1060" class="nota">'
        "1:N = um para muitos · 0..1 = relacionamento opcional · "
        "linhas tracejadas = vínculo opcional ou elemento conceitual/derivado."
        "</text>"
        '<text x="50" y="1085" class="nota">'
        "Atendimentos e referências distritais são simulados. "
        "Totais do IBGE são municipais e independentes das demais entidades."
        "</text>"
        '<text x="1550" y="1085" text-anchor="end" class="nota">'
        "EquiDados · CESAR School</text></svg>"
    )
    return "".join(partes)


def gerar_pdf():
    if not EDGE.is_file():
        raise FileNotFoundError(
            f"Microsoft Edge não encontrado para exportar o PDF: {EDGE}"
        )

    documento = f"""<!doctype html>
    <html lang="pt-BR"><head><meta charset="utf-8">
    <title>EquiDados — Modelo Conceitual — Última versão</title>
    <style>
      @page {{ size: A3 landscape; margin: 0; }}
      html, body {{ margin: 0; padding: 0; width: 420mm; height: 297mm;
          background: #f7f5fa; }}
      svg {{ display: block; width: 420mm; height: 297mm; }}
    </style></head><body>{criar_svg()}</body></html>"""

    with tempfile.TemporaryDirectory(prefix="equidados-modelo-conceitual-") as pasta:
        pasta_temporaria = Path(pasta)
        arquivo_html = pasta_temporaria / "modelo.html"
        arquivo_html.write_text(documento, encoding="utf-8")
        subprocess.run(
            [
                str(EDGE),
                "--headless",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={pasta_temporaria / 'edge-profile'}",
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
