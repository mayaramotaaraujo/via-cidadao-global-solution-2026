"""Zelo, zeladoria urbana com IA (front-end Streamlit).

Rodar localmente (a partir da pasta frontend/):
    streamlit run app.py

Este arquivo só monta o layout (cabeçalho, barra lateral e abas). Cada tela
vive em features/, componentes visuais em ui/, estado em state/ e o acesso
à API em providers/.
"""

import streamlit as st

st.set_page_config(page_title="Zelo | Zeladoria urbana de São Paulo", page_icon=":material/signpost:", layout="wide")

from features import gestor, meus_relatos, painel, relatar, sobre  # noqa: E402
from providers.api_client import aguardar_servico, verificar_saude  # noqa: E402
from state import sessao  # noqa: E402
from ui.tema import aplicar_tema  # noqa: E402

sessao.inicializar()
aplicar_tema(st.session_state.alto_contraste, st.session_state.fonte_grande)

# ------------------------------------------------------------- cabeçalho
# O espaço fica reservado no topo e é preenchido por último, para mostrar o estado
# real do serviço depois de a tela principal ter acordado a API (plano gratuito).
espaco_cabecalho = st.empty()


def desenhar_cabecalho() -> None:
    online = verificar_saude()
    situacao = (
        '<span class="zl-situacao" style="--c:#1E7B34">Serviço online</span>'
        if online
        else '<span class="zl-situacao" style="--c:#B3261E">Serviço indisponível no momento</span>'
    )
    aviso = (
        ""
        if online
        else '<p class="zl-rodape">Você pode consultar as informações, mas o envio de relatos pode falhar até o serviço voltar.</p>'
    )
    espaco_cabecalho.markdown(
        f"""
        <header class="zl-cabecalho">
          <div class="zl-marca">
            <span class="zl-placa zl-placa--logo">Zelo</span>
            <div class="zl-marca__texto">
              <strong>Zeladoria urbana de São Paulo</strong>
              <span>Registre problemas em ruas, calçadas e praças e acompanhe o atendimento pelo protocolo.</span>
            </div>
          </div>
          {situacao}
        </header>
        {aviso}
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------- barra lateral
with st.sidebar:
    st.radio("Acessar como", ["Cidadão", "Gestor"], key="perfil", horizontal=True)
    if st.session_state.perfil == "Gestor":
        with st.form("login_gestor", clear_on_submit=True):
            token = st.text_input("Código de acesso da equipe", type="password")
            if st.form_submit_button("Entrar"):
                st.session_state.gestor_token = token or None
        if st.session_state.gestor_token:
            st.caption("Acesso de gestor ativo nesta sessão.")
            if st.button("Sair da área de gestão"):
                st.session_state.gestor_token = None
                st.rerun()

    st.divider()
    st.markdown("**Acessibilidade**")
    st.toggle("Alto contraste", key="alto_contraste")
    st.toggle("Fonte maior", key="fonte_grande")

    st.divider()
    st.markdown("**Em caso de emergência**")
    st.markdown(
        '<dl class="zl-telefones"><dt>Polícia Militar</dt><dd>190</dd><dt>SAMU</dt><dd>192</dd>'
        "<dt>Bombeiros</dt><dd>193</dd><dt>Defesa Civil</dt><dd>199</dd></dl>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown('<p class="zl-rodape">Protótipo acadêmico da FIAP para a Global Solution 2026.2.</p>',
                unsafe_allow_html=True)

# ------------------------------------------------------------------ abas
# Na primeira visita a API pode estar hibernada: esperamos ela acordar (uma vez por sessão).
if not st.session_state.api_verificada:
    with st.spinner("Conectando ao serviço. Na primeira visita isso pode levar até 1 minuto."):
        aguardar_servico()
    st.session_state.api_verificada = True

nomes = ["Registrar problema", "Meus protocolos", "Painel da cidade", "Como funciona"]
telas = [relatar.render, meus_relatos.render, painel.render, sobre.render]
if st.session_state.perfil == "Gestor":
    nomes.insert(3, "Gestão")
    telas.insert(3, gestor.render)

for aba, tela in zip(st.tabs(nomes), telas):
    with aba:
        tela()

desenhar_cabecalho()
