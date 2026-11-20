"""Componentes visuais reutilizáveis.

Cada função aqui é usada em mais de uma tela ou com parâmetros diferentes
(ex.: `badge_urgencia` aparece no resultado da IA, no histórico, na gestão
e na página "Como funciona"). Todo texto vindo do usuário ou da IA passa por
`html.escape` antes de ir para HTML, evitando injeção de código (XSS).
"""

import html
import json

import streamlit as st

from providers.api_client import ErroAPI
from ui.rotulos import URGENCIAS, rotulo_categoria, rotulo_status

# Formas da sinalização de trânsito brasileira, uma por nível de urgência:
# octógono (PARE), triângulo (dê a preferência), losango (advertência), quadrado (informativa).
_FORMAS = {
    "octogono": '<polygon points="4.7,0 11.3,0 16,4.7 16,11.3 11.3,16 4.7,16 0,11.3 0,4.7"/>',
    "triangulo": '<polygon points="8,0.5 16,15.5 0,15.5"/>',
    "losango": '<polygon points="8,0 16,8 8,16 0,8"/>',
    "quadrado": '<rect x="1" y="1" width="14" height="14" rx="1.5"/>',
}


def badge_urgencia(nivel: str, grande: bool = False, com_descricao: bool = False) -> str:
    """HTML do selo de urgência: cor + forma de placa + nome escrito."""
    u = URGENCIAS.get(nivel)
    if not u:
        return ""
    classe = "zl-urg zl-urg--grande" if grande else "zl-urg"
    forma = f'<svg viewBox="0 0 16 16" fill="#fff" aria-hidden="true">{_FORMAS[u["forma"]]}</svg>'
    selo = f'<span class="{classe}" style="background:{u["cor"]}">{forma}Urgência {u["rotulo"].lower()}</span>'
    if com_descricao:
        selo += f'<span class="zl-urg-desc">{u["descricao"]}</span>'
    return selo


def mostrar_badge_urgencia(nivel: str, grande: bool = False, com_descricao: bool = False) -> None:
    st.markdown(badge_urgencia(nivel, grande, com_descricao), unsafe_allow_html=True)


def dados(pares: list[tuple[str, str]]) -> None:
    """Lista de rótulo/valor em grade. Valores já devem vir escapados ou ser HTML confiável."""
    itens = "".join(f"<div><dt>{html.escape(r)}</dt><dd>{v}</dd></div>" for r, v in pares)
    st.markdown(f'<dl class="zl-dados">{itens}</dl>', unsafe_allow_html=True)


def etapas(atual: int) -> None:
    """Indicador das 3 etapas do registro (é uma sequência real, por isso numerada)."""
    nomes = ["Descreva o problema", "Confira a análise", "Receba o protocolo"]
    itens = []
    for i, nome in enumerate(nomes):
        classe = "atual" if i == atual else ("feita" if i < atual else "")
        aria = ' aria-current="step"' if i == atual else ""
        itens.append(f'<li class="{classe}"{aria}><span>{i + 1}</span>{nome}</li>')
    st.markdown(f'<ol class="zl-etapas">{"".join(itens)}</ol>', unsafe_allow_html=True)


def placa_protocolo(protocolo: str) -> None:
    st.markdown(
        f'<div class="zl-placa zl-placa--protocolo" role="group" aria-label="Número do protocolo">'
        f"<small>Protocolo</small><strong>{html.escape(protocolo)}</strong></div>",
        unsafe_allow_html=True,
    )


def cartao_relato(relato: dict, mostrar_descricao: bool = False, mostrar_orientacoes: bool = False) -> None:
    """Cartão de um relato. Usado em 'Meus protocolos' (cidadão) e na 'Gestão'."""
    with st.container(border=True):
        st.markdown(
            f'<div class="zl-relato__topo"><span class="zl-protocolo">{html.escape(relato["protocolo"])}</span>'
            f'{badge_urgencia(relato["urgencia"])}</div>'
            f'<p class="zl-relato__resumo">{html.escape(relato.get("resumo", ""))}</p>',
            unsafe_allow_html=True,
        )
        dados([
            ("Tipo", html.escape(rotulo_categoria(relato["categoria"]))),
            ("Bairro", html.escape(relato["bairro"])),
            ("Situação", html.escape(rotulo_status(relato.get("status", "recebido")))),
            ("Responsável", html.escape(relato.get("orgao_responsavel", "Não informado"))),
            ("Prazo de referência", f'{relato.get("prazo_estimado_dias", "?")} dia(s)'),
        ])
        if mostrar_descricao and relato.get("descricao_anonimizada"):
            st.markdown("**Relato do cidadão**, com dados pessoais removidos")
            st.text(relato["descricao_anonimizada"])
        if mostrar_orientacoes and relato.get("orientacoes_cidadao"):
            with st.expander("Orientações até o reparo"):
                for o in relato["orientacoes_cidadao"]:
                    st.markdown(f"- {html.escape(o)}")


def metrica(titulo: str, valor, ajuda: str | None = None, delta: str | None = None) -> None:
    st.metric(titulo, valor, delta=delta, help=ajuda, border=True)


def estado_vazio(titulo: str, texto: str) -> None:
    st.markdown(
        f'<div class="zl-vazio" role="note"><strong>{html.escape(titulo)}</strong>'
        f"<p>{html.escape(texto)}</p></div>",
        unsafe_allow_html=True,
    )


def mostrar_erro(erro: ErroAPI, acao: str | None = None) -> None:
    """Mensagem de erro clara. Nunca mostra detalhes técnicos ao cidadão."""
    texto = f"**{erro.mensagem}**"
    if erro.campos:
        texto += "\n\n" + "\n".join(f"- **{html.escape(c)}**: {html.escape(m)}" for c, m in erro.campos.items())
    if acao:
        texto += f"\n\n{acao}"
    st.error(texto, icon=":material/error:")


def botao_ouvir(texto: str) -> None:
    """Leitura em voz alta (Web Speech API do navegador, pt-BR). Sem custo e sem dependências."""
    texto_js = html.escape(json.dumps(texto), quote=True)
    st.html(
        f"""
        <button type="button" aria-label="Ouvir as orientações em voz alta"
          onclick="(function(){{const s=window.speechSynthesis;s.cancel();
            const u=new SpeechSynthesisUtterance({texto_js});u.lang='pt-BR';u.rate=0.95;s.speak(u);}})()"
          style="display:inline-flex;align-items:center;gap:8px;font:600 15px 'Public Sans',system-ui,sans-serif;
                 padding:9px 16px;border-radius:6px;border:1px solid #0F4C97;background:#fff;color:#0F4C97;cursor:pointer">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="#0F4C97" aria-hidden="true">
            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v2.1a7 7 0 0 1 0 13.4v2.1a9 9 0 0 0 0-17.6z"/>
          </svg>
          Ouvir orientações
        </button>
        """,
        unsafe_allow_javascript=True,
    )
