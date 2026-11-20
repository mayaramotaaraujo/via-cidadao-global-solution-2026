"""Visão do gestor (RBAC): fila priorizada por urgência e tratamento dos relatos.

Segundo nível de human-in-the-loop: o servidor público revisa a classificação
da IA (e a correção do cidadão) antes de encaminhar a equipe.
"""

import html

import pandas as pd
import streamlit as st

from providers.api_client import ErroAPI, carregar_relatos_publicos, obter_cliente
from ui.componentes import cartao_relato, estado_vazio, metrica, mostrar_erro
from ui.rotulos import ORDEM_URGENCIA, STATUS, rotulo_categoria, rotulo_status, rotulo_urgencia


def render() -> None:
    token = st.session_state.get("gestor_token")
    if not token:
        estado_vazio("Área restrita à equipe", "Informe o código de acesso da equipe na barra lateral.")
        return

    try:
        relatos = obter_cliente().gestor_listar(token)
    except ErroAPI as e:
        if e.codigo == "NAO_AUTORIZADO":
            st.session_state.gestor_token = None
        mostrar_erro(e)
        return

    abertos = [r for r in relatos if r["status"] not in ("resolvido", "rejeitado")]
    c1, c2, c3, _ = st.columns(4)
    with c1:
        metrica("Em aberto", len(abertos))
    with c2:
        metrica("Críticos em aberto", sum(r["urgencia"] == "critica" for r in abertos))
    with c3:
        metrica("Corrigidos pelo cidadão", sum(bool(r["ia_corrigida"]) for r in relatos))

    status_filtro = st.multiselect(
        "Situação", list(STATUS), default=["recebido", "em_analise", "encaminhado"], format_func=rotulo_status,
        key="gs_status",
    )
    fila = [r for r in relatos if r["status"] in status_filtro]
    # Prioridade: urgência (crítica primeiro) e depois o mais antigo.
    fila.sort(key=lambda r: (ORDEM_URGENCIA.index(r["urgencia"]), r["criado_em"]))
    if not fila:
        estado_vazio("Nenhum relato nesta situação", "Altere o filtro de situação para ver outros relatos.")
        return

    st.markdown("##### Fila por prioridade")
    tabela = pd.DataFrame(fila)
    tabela["Urgência"] = tabela["urgencia"].map(rotulo_urgencia)
    tabela["Tipo"] = tabela["categoria"].map(rotulo_categoria)
    tabela["Situação"] = tabela["status"].map(rotulo_status)
    tabela["Corrigido pelo cidadão"] = tabela["ia_corrigida"].map({True: "Sim", False: "Não", 1: "Sim", 0: "Não"})
    st.dataframe(
        tabela[["protocolo", "Urgência", "Tipo", "bairro", "Situação", "Corrigido pelo cidadão"]].rename(
            columns={"protocolo": "Protocolo", "bairro": "Bairro"}
        ),
        hide_index=True, width="stretch",
    )

    st.markdown("##### Tratar relato")
    protocolo = st.selectbox("Protocolo", [r["protocolo"] for r in fila], key="gs_sel")
    relato = next(r for r in fila if r["protocolo"] == protocolo)
    cartao_relato(relato, mostrar_descricao=True)

    if relato["ia_corrigida"]:
        st.info(
            f"O cidadão corrigiu a IA. A sugestão original era {rotulo_categoria(relato['categoria_ia'])}, "
            f"urgência {rotulo_urgencia(relato['urgencia_ia']).lower()}, com confiança de {relato['confianca_ia']:.0%}.",
            icon=":material/edit_note:",
        )
    if relato.get("nota_gestor"):
        st.caption(f"Última nota da equipe: {html.escape(relato['nota_gestor'])}")

    with st.form(f"form_status_{protocolo}", border=False):
        c1, c2 = st.columns([1, 2])
        novo = c1.selectbox("Nova situação", list(STATUS), index=list(STATUS).index(relato["status"]), format_func=rotulo_status)
        nota = c2.text_input("Nota para o registro", max_chars=300, placeholder="Opcional")
        if st.form_submit_button("Salvar situação", type="primary"):
            try:
                obter_cliente().gestor_atualizar(token, protocolo, novo, nota)
                carregar_relatos_publicos.clear()
                st.toast(f"Situação de {protocolo} salva como {rotulo_status(novo).lower()}.", icon=":material/check:")
                st.rerun()
            except ErroAPI as e:
                mostrar_erro(e)
