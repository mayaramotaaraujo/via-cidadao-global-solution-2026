"""Histórico do cidadão nesta sessão (mantido em st.session_state)."""

import pandas as pd
import plotly.express as px
import streamlit as st

from features.relatar import avaliacao_ia
from providers.api_client import ErroAPI, obter_cliente
from state import sessao
from ui.componentes import cartao_relato, estado_vazio, metrica, mostrar_erro
from ui.graficos import estilizar
from ui.rotulos import MAPA_CORES_URGENCIA, ORDEM_URGENCIA, URGENCIAS, rotulo_urgencia


def render() -> None:
    historico = sessao.historico()
    if not historico:
        estado_vazio(
            "Nenhum protocolo nesta sessão",
            "Os problemas que você registrar aparecem aqui, com o número do protocolo e a situação do atendimento.",
        )
        return

    c1, c2, c3, _ = st.columns([1, 1, 1, 1])
    with c1:
        metrica("Protocolos", len(historico))
    with c2:
        metrica("Urgência alta ou crítica", sum(r["urgencia"] in ("alta", "critica") for r in historico))
    with c3:
        metrica("Resolvidos", sum(r.get("status") == "resolvido" for r in historico))

    if st.button("Atualizar situação", icon=":material/refresh:"):
        try:
            with st.spinner("Consultando a situação dos protocolos"):
                for r in historico:
                    sessao.atualizar_no_historico(obter_cliente().obter_relato(r["protocolo"]))
            st.toast("Situação atualizada.", icon=":material/check:")
        except ErroAPI as e:
            mostrar_erro(e)

    # Gráfico alimentado pelo histórico guardado no estado da sessão
    df = pd.DataFrame(historico)
    df["Urgência"] = df["urgencia"].map(lambda u: URGENCIAS[u]["rotulo"])
    contagem = df.groupby("Urgência").size().reindex([URGENCIAS[u]["rotulo"] for u in ORDEM_URGENCIA]).dropna()
    fig = px.bar(
        contagem.reset_index(name="Protocolos"), x="Urgência", y="Protocolos", color="Urgência", text="Protocolos",
        color_discrete_map=MAPA_CORES_URGENCIA,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_yaxes(dtick=1)
    st.markdown("##### Seus protocolos por urgência")
    st.plotly_chart(estilizar(fig, altura=240, legenda=False), width="stretch")

    filtro = st.multiselect(
        "Filtrar por urgência", ORDEM_URGENCIA, default=ORDEM_URGENCIA, format_func=rotulo_urgencia, key="filtro_meus"
    )
    for relato in [r for r in historico if r["urgencia"] in filtro]:
        cartao_relato(relato, mostrar_orientacoes=True)
        avaliacao_ia(relato["protocolo"], chave="historico")
