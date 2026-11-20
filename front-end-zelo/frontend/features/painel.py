"""Painel da cidade: visão agregada e transparente dos relatos (sem dados pessoais)."""

import pandas as pd
import plotly.express as px
import streamlit as st

from providers.api_client import ErroAPI, carregar_relatos_publicos
from ui.componentes import estado_vazio, metrica, mostrar_erro
from ui.graficos import estilizar
from ui.rotulos import (
    CATEGORIAS,
    MAPA_CORES_URGENCIA,
    ORDEM_URGENCIA,
    URGENCIAS,
    rotulo_categoria,
    rotulo_status,
    rotulo_urgencia,
)

PERIODOS = {"Últimos 7 dias": 7, "Últimos 15 dias": 15, "Últimos 30 dias": 30, "Todo o período": None}


def _preparar(registros: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(registros)
    df["criado_em"] = pd.to_datetime(df["criado_em"], utc=True, format="ISO8601")
    df["dia"] = df["criado_em"].dt.tz_convert("America/Sao_Paulo").dt.date
    df["Urgência"] = df["urgencia"].map(lambda u: URGENCIAS[u]["rotulo"])
    df["Tipo"] = df["categoria"].map(rotulo_categoria)
    df["Situação"] = df["status"].map(rotulo_status)
    return df


def render() -> None:
    st.markdown("Relatos confirmados pelos cidadãos, sem nenhum dado pessoal.")

    # ------------------------------------------------------------ filtros
    f1, f2, f3, f4 = st.columns([1.3, 2, 1.6, 1.3])
    periodo = f1.selectbox("Período", list(PERIODOS), index=2, key="pn_periodo")
    cats = f2.multiselect(
        "Tipo de problema", list(CATEGORIAS), format_func=rotulo_categoria, key="pn_cats", placeholder="Todos",
    )
    urgs = f3.multiselect("Urgência", ORDEM_URGENCIA, format_func=rotulo_urgencia, key="pn_urgs", placeholder="Todas")

    try:
        incluir_sim = st.session_state.get("pn_sim", True)
        registros = carregar_relatos_publicos(incluir_sim)
    except ErroAPI as e:
        mostrar_erro(e, "O painel volta a carregar assim que o serviço responder.")
        if st.button("Tentar de novo", key="retry_painel"):
            carregar_relatos_publicos.clear()
            st.rerun()
        return

    bairros = sorted({r["bairro"] for r in registros})
    bairro_sel = f4.selectbox("Bairro", ["Todos"] + bairros, key="pn_bairro")
    st.toggle(
        "Incluir relatos simulados", value=True, key="pn_sim",
        help="O painel começa com relatos simulados para demonstração. Desligue para ver apenas relatos reais.",
    )

    if not registros:
        estado_vazio("Ainda não há relatos", "Registre o primeiro problema na aba Registrar problema.")
        return

    df = _preparar(registros)
    if PERIODOS[periodo]:
        corte = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=PERIODOS[periodo])
        df = df[df["criado_em"] >= corte]
    if cats:
        df = df[df["categoria"].isin(cats)]
    if urgs:
        df = df[df["urgencia"].isin(urgs)]
    if bairro_sel != "Todos":
        df = df[df["bairro"] == bairro_sel]

    if df.empty:
        estado_vazio("Nenhum relato com esses filtros", "Amplie o período ou remova algum filtro.")
        return

    # ---------------------------------------------------------- indicadores
    total = len(df)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metrica("Relatos", total)
    with c2:
        metrica("Urgência crítica", int((df["urgencia"] == "critica").sum()), "Risco imediato à vida ou à integridade física.")
    with c3:
        metrica("Resolvidos", f"{(df['status'] == 'resolvido').mean():.0%}")
    with c4:
        metrica(
            "Correções da IA", f"{df['ia_corrigida'].mean():.0%}",
            "Parte dos relatos em que o cidadão corrigiu a classificação da IA. É o indicador de qualidade da IA.",
        )
    if df["simulado"].any():
        st.caption(f"{int(df['simulado'].sum())} dos {total} relatos exibidos são simulados para demonstração.")

    ordem_urg = [URGENCIAS[u]["rotulo"] for u in ORDEM_URGENCIA]
    aba_tipo, aba_tempo, aba_mapa, aba_tabela = st.tabs(["Por tipo", "Por dia", "Mapa", "Tabela"])

    with aba_tipo:
        agrupado = df.groupby(["Tipo", "Urgência"]).size().reset_index(name="Relatos")
        fig = px.bar(
            agrupado, x="Relatos", y="Tipo", color="Urgência", orientation="h",
            pattern_shape="Urgência",  # textura além da cor: legível para pessoas daltônicas
            color_discrete_map=MAPA_CORES_URGENCIA, category_orders={"Urgência": ordem_urg},
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending", "title": ""}, bargap=0.42)
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(estilizar(fig, altura=420), width="stretch")

    with aba_tempo:
        serie = df.groupby(["dia", "Urgência"]).size().reset_index(name="Relatos")
        fig = px.line(
            serie, x="dia", y="Relatos", color="Urgência", markers=True, symbol="Urgência",
            color_discrete_map=MAPA_CORES_URGENCIA, category_orders={"Urgência": ordem_urg}, labels={"dia": ""},
        )
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(estilizar(fig, altura=380), width="stretch")

    with aba_mapa:
        fig = px.scatter_map(
            df, lat="latitude", lon="longitude", color="Urgência", color_discrete_map=MAPA_CORES_URGENCIA,
            category_orders={"Urgência": ordem_urg},
            hover_name="protocolo", hover_data={"Tipo": True, "bairro": True, "Situação": True,
                                                "latitude": False, "longitude": False},
            zoom=9.3, map_style="carto-positron",
        )
        fig.update_traces(marker={"size": 11, "opacity": 0.9})
        st.plotly_chart(estilizar(fig, altura=480), width="stretch")
        st.caption("Por privacidade, cada ponto fica perto do centro do bairro, e não no endereço exato.")

    with aba_tabela:
        st.dataframe(
            df.sort_values("criado_em", ascending=False)[
                ["protocolo", "criado_em", "bairro", "Tipo", "Urgência", "Situação", "orgao_responsavel"]
            ].rename(columns={"protocolo": "Protocolo", "criado_em": "Data", "bairro": "Bairro",
                              "orgao_responsavel": "Órgão responsável"}),
            hide_index=True, width="stretch",
            column_config={"Data": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm")},
        )
