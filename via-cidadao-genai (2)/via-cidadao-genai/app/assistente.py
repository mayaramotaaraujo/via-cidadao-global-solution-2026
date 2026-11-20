"""Tela do assistente no Streamlit (VIA CIDADÃO, módulo VIA INTELIGÊNCIA).


"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import streamlit as st  # noqa: E402

from integracao import orientar_ocorrencia  # noqa: E402
from pipeline import Assistente  # noqa: E402

st.set_page_config(page_title="VIA CIDADÃO, assistente", page_icon="🏙️", layout="centered")


@st.cache_resource
def carregar():
    return Assistente(modo_geracao=os.getenv("VIA_GERACAO", "extrativo"))


assistente = carregar()

st.title("Assistente do VIA CIDADÃO")
st.caption("Tire dúvidas sobre como pedir serviços da prefeitura e sobre acessibilidade. "
           "As respostas vêm só das fontes cadastradas, que aparecem abaixo de cada resposta. "
           "Isto não substitui os canais oficiais nem os serviços de emergência.")

if "historico" not in st.session_state:
    st.session_state.historico = []      # perguntas feitas
    st.session_state.mensagens = []      # o que aparece na tela

with st.sidebar:
    st.subheader("Ocorrência de exemplo")
    st.write("Mostra como o assistente lê uma ocorrência registrada pelos outros módulos.")
    categoria = st.selectbox("Categoria", ["poste_apagado", "buraco", "bueiro_entupido", "calcada_sem_rampa"])
    if st.button("Orientar esta ocorrência"):
        r = orientar_ocorrencia({"id": "VIA-0001", "categoria": categoria}, assistente)
        st.session_state.mensagens.append(("assistente", f"Ocorrência {r['ocorrencia_id']}: {r['orientacao']}", None))
    if st.button("Limpar conversa"):
        st.session_state.historico, st.session_state.mensagens = [], []

for papel, texto, info in st.session_state.mensagens:
    with st.chat_message(papel):
        st.write(texto)
        if info:
            with st.expander("Ver trechos usados e detalhes"):
                st.write(f"Situação: {info['status']}")
                for t in info["trechos"]:
                    st.markdown(f"**{t['id']}** ({t['secao']}), nota {t['nota']:.3f}")
                    st.write(t["corpo"] if "corpo" in t else t["texto"])
                if info["removidos_por_suspeita"]:
                    st.warning("Trechos retirados por conterem ordens suspeitas: "
                               + ", ".join(info["removidos_por_suspeita"]))

pergunta = st.chat_input("Escreva sua dúvida")
if pergunta:
    r = assistente.responder(pergunta, st.session_state.historico)
    st.session_state.historico.append(pergunta)
    st.session_state.mensagens.append(("user", pergunta, None))
    st.session_state.mensagens.append(("assistente", r["resposta"], r))
    st.rerun()
