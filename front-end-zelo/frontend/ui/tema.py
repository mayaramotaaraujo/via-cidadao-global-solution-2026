"""Identidade visual do Zelo e ajustes de acessibilidade.

Referência: as placas de nome de rua de São Paulo (azul, letra branca,
filete branco interno) e as formas da sinalização de trânsito.
"""

import streamlit as st

_BASE = """
<style>
  :root {
    --zl-azul: #0F4C97;
    --zl-tinta: #1A2533;
    --zl-asfalto: #5B6675;
    --zl-meiofio: #DCE1E7;
    --zl-calcada: #F4F6F8;
  }

  .block-container {max-width: 1160px; padding-top: 2rem; padding-bottom: 4rem}
  [data-testid="stHeaderActionElements"] {display: none}   /* ícones de link nos títulos */
  .stApp p, .stApp li {line-height: 1.55}

  /* Cabeçalho ------------------------------------------------------------ */
  .zl-cabecalho {display: flex; align-items: center; justify-content: space-between; gap: 24px;
                 padding-bottom: 20px; margin-bottom: 4px; border-bottom: 1px solid var(--zl-meiofio)}
  .zl-marca {display: flex; align-items: center; gap: 18px}
  .zl-marca__texto strong {display: block; font-size: 1.0625rem; font-weight: 650; color: var(--zl-tinta)}
  .zl-marca__texto span {display: block; font-size: .9375rem; color: var(--zl-asfalto); max-width: 60ch}
  .zl-situacao {display: inline-flex; align-items: center; gap: 8px; font-size: .875rem;
                color: var(--zl-asfalto); white-space: nowrap}
  .zl-situacao::before {content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--c)}

  /* A placa: elemento de identidade (logo e protocolo) --------------------- */
  .zl-placa {display: inline-flex; flex-direction: column; justify-content: center;
             background: var(--zl-azul); color: #fff; border-radius: 6px; padding: 7px 16px;
             box-shadow: inset 0 0 0 3px var(--zl-azul), inset 0 0 0 5px #fff;
             font-weight: 700; letter-spacing: .01em; line-height: 1.1}
  .zl-placa--logo {font-size: 1.375rem; padding: 8px 18px}
  .zl-placa--protocolo {padding: 14px 26px 16px; margin: 4px 0 12px}
  .zl-placa--protocolo small {font-size: .8125rem; font-weight: 500; opacity: .9; margin-bottom: 4px}
  .zl-placa--protocolo strong {font-size: 2rem; font-variant-numeric: tabular-nums; letter-spacing: .02em}

  /* Etapas do registro (sequência real: 1 → 2 → 3) ------------------------- */
  .zl-etapas {display: flex; gap: 28px; list-style: none; padding: 0; margin: 4px 0 20px; flex-wrap: wrap}
  .zl-etapas li {display: flex; align-items: center; gap: 10px; color: var(--zl-asfalto); font-size: .9375rem; margin: 0}
  .zl-etapas li span {display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 50%;
                      border: 1.5px solid var(--zl-meiofio); font-size: .8125rem; font-weight: 600}
  .zl-etapas li.atual {color: var(--zl-tinta); font-weight: 600}
  .zl-etapas li.atual span {background: var(--zl-azul); border-color: var(--zl-azul); color: #fff}
  .zl-etapas li.feita span {border-color: var(--zl-azul); color: var(--zl-azul)}

  /* Selo de urgência ------------------------------------------------------ */
  .zl-urg {display: inline-flex; align-items: center; gap: 7px; color: #fff; font-weight: 600;
           font-size: .875rem; line-height: 1; padding: 6px 10px 6px 8px; border-radius: 4px; white-space: nowrap}
  .zl-urg svg {width: 13px; height: 13px; flex: none}
  .zl-urg--grande {font-size: 1rem; padding: 8px 12px 8px 10px}
  .zl-urg--grande svg {width: 15px; height: 15px}
  .zl-urg-desc {color: var(--zl-asfalto); font-size: .9375rem; margin-left: 10px}

  /* Dados em pares (rótulo / valor) -------------------------------------- */
  .zl-dados {display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px 28px; margin: 4px 0 20px}
  .zl-dados dt {font-size: .8125rem; color: var(--zl-asfalto); margin-bottom: 4px; font-weight: 500}
  .zl-dados dd {margin: 0; color: var(--zl-tinta); font-weight: 500}

  /* Relato em lista ----------------------------------------------------- */
  .zl-relato__topo {display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 6px}
  .zl-protocolo {font-weight: 650; font-variant-numeric: tabular-nums; color: var(--zl-tinta)}
  .zl-relato__resumo {font-size: 1.0625rem; margin: 0 0 14px; color: var(--zl-tinta)}

  /* Estado vazio --------------------------------------------------------- */
  .zl-vazio {background: var(--zl-calcada); border-radius: 6px; padding: 28px 28px 24px; max-width: 640px}
  .zl-vazio strong {display: block; font-size: 1.0625rem; margin-bottom: 4px; color: var(--zl-tinta)}
  .zl-vazio p {margin: 0; color: var(--zl-asfalto)}

  /* Barra lateral ------------------------------------------------------ */
  .zl-telefones {display: grid; grid-template-columns: 1fr auto; gap: 6px 12px; font-size: .875rem; margin: 0}
  .zl-telefones dt {color: var(--zl-asfalto)}
  .zl-telefones dd {margin: 0; font-weight: 650; font-variant-numeric: tabular-nums}
  .zl-rodape {font-size: .8125rem; color: var(--zl-asfalto)}

  /* Componentes nativos -------------------------------------------------- */
  [data-testid="stMetric"] {background: #fff; padding: 14px 16px 12px}
  [data-testid="stMetricLabel"] p {color: var(--zl-asfalto); font-size: .875rem}
  .stTabs [data-baseweb="tab-list"], .stTabs [role="tablist"] {gap: 32px !important}
  .stTabs [data-baseweb="tab"] {padding-left: 0; padding-right: 0; font-weight: 500}
  .stTabs [aria-selected="true"] {color: var(--zl-azul); font-weight: 600}

  /* Foco sempre visível para quem navega pelo teclado (WCAG 2.4.7) */
  .stApp button:focus-visible, .stApp input:focus-visible, .stApp textarea:focus-visible,
  .stApp [role="tab"]:focus-visible, .stApp [role="radio"]:focus-visible, .stApp a:focus-visible {
    outline: 3px solid var(--zl-azul) !important; outline-offset: 2px}

  @media (max-width: 720px) {
    .zl-cabecalho {flex-direction: column; align-items: flex-start}
    .zl-placa--protocolo strong {font-size: 1.5rem}
  }
  @media (prefers-reduced-motion: reduce) {* {transition: none !important; animation: none !important}}
</style>
"""

_FONTE_GRANDE = """
<style>
  .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .zl-dados dd {font-size: 1.1875rem !important}
  .zl-urg {font-size: 1rem}
</style>
"""

# Alto contraste mantendo o fundo branco: texto preto puro, bordas fortes, links sublinhados.
_ALTO_CONTRASTE = """
<style>
  :root {--zl-tinta: #000; --zl-asfalto: #000; --zl-meiofio: #000}
  .stApp, .stApp p, .stApp label, .stApp li, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp dd, .stApp dt {color: #000 !important}
  .stApp .zl-urg, .stApp .zl-urg span, .stApp .zl-placa, .stApp .zl-placa *,
  .stApp [data-testid="stBaseButton-primary"], .stApp [data-testid="stBaseButton-primary"] *,
  .stApp [data-testid="stBaseButton-primaryFormSubmit"], .stApp [data-testid="stBaseButton-primaryFormSubmit"] * {color: #fff !important}
  .stApp a {text-decoration: underline !important}
  .stApp [data-testid="stVerticalBlockBorderWrapper"], .stApp input, .stApp textarea,
  .stApp [data-baseweb="select"] > div, .stApp button {border: 2px solid #000 !important}
  .zl-urg {outline: 2px solid #000; outline-offset: 1px}
  .zl-vazio {background: #fff; border: 2px solid #000}
</style>
"""


def aplicar_tema(alto_contraste: bool, fonte_grande: bool) -> None:
    st.markdown(_BASE, unsafe_allow_html=True)
    if fonte_grande:
        st.markdown(_FONTE_GRANDE, unsafe_allow_html=True)
    if alto_contraste:
        st.markdown(_ALTO_CONTRASTE, unsafe_allow_html=True)
