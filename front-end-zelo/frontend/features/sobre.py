"""Como funciona, privacidade e limites da IA, em linguagem simples."""

import streamlit as st

from ui.componentes import badge_urgencia
from ui.rotulos import ORDEM_URGENCIA, URGENCIAS


def render() -> None:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("#### Como funciona")
        st.markdown(
            """
1. Você descreve o problema com suas palavras e informa o bairro.
2. A inteligência artificial indica o tipo, a urgência e o órgão responsável. Você confere e pode corrigir.
3. Você recebe um protocolo para acompanhar o atendimento.
"""
        )
        st.markdown("#### Seus dados")
        st.markdown(
            """
- Telefone, CPF, e-mail e placas de veículo são removidos do texto antes da análise.
- O serviço não pede seu nome nem seu endereço.
- O painel público mostra apenas o resumo do problema, nunca o texto que você escreveu.
"""
        )
    with c2:
        st.markdown("#### Limites da inteligência artificial")
        st.markdown(
            """
- Não substitui a Defesa Civil, os Bombeiros nem a Polícia.
- Os prazos exibidos são de referência e não garantem a data do reparo.
- A IA pode errar. Por isso você confirma a análise antes do protocolo, e a equipe da Prefeitura revisa o pedido.
"""
        )
        st.markdown("#### Níveis de urgência")
        linhas = "".join(
            f'<div style="display:flex;align-items:center;gap:12px;margin:0 0 10px">{badge_urgencia(u)}'
            f'<span style="color:var(--zl-asfalto)">{URGENCIAS[u]["descricao"]}</span></div>'
            for u in ORDEM_URGENCIA
        )
        st.markdown(linhas, unsafe_allow_html=True)
        st.caption("Cada nível tem cor, forma de placa de trânsito e nome escrito, para não depender só da cor.")

    with st.expander("Recursos de acessibilidade"):
        st.markdown(
            """
- Alto contraste e fonte maior, na barra lateral.
- Leitura em voz alta das orientações.
- Navegação por teclado com foco sempre visível.
- Urgência indicada por cor, forma e nome; gráficos com texturas e símbolos além das cores.
- Rótulos e textos de ajuda em todos os campos.
"""
        )
