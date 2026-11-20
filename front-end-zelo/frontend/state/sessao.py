"""Estado centralizado da sessão (st.session_state).

Toda leitura/escrita de estado passa por estas funções. Assim, as telas
(features/) não espalham chaves mágicas pelo código e fica fácil saber
o que sobrevive a cada rerun do Streamlit.
"""

from datetime import datetime

import streamlit as st

# Etapas do fluxo do cidadão (máquina de estados simples)
FORMULARIO, REVISAO, CONCLUIDO = "formulario", "revisao", "concluido"

_PADROES = {
    "etapa": FORMULARIO,
    "analise_atual": None,      # resposta da IA aguardando confirmação humana
    "entrada_atual": None,      # o que o cidadão digitou (para editar sem perder)
    "relato_confirmado": None,  # último protocolo gerado
    "historico": [],            # protocolos do cidadão nesta sessão
    "feedbacks": {},            # protocolo -> "util" | "incorreto"
    "perfil": "Cidadão",
    "gestor_token": None,
    "alto_contraste": False,
    "fonte_grande": False,
    "api_verificada": False,    # já esperamos a API acordar nesta sessão
    # widgets do formulário (chaves fixas permitem preencher com exemplo)
    "campo_descricao": "",
    "campo_bairro": None,
    "campo_referencia": "",
    "campo_consentimento": False,
}


def inicializar() -> None:
    for chave, valor in _PADROES.items():
        if chave not in st.session_state:
            # cópia para não compartilhar listas/dicts mutáveis entre sessões
            st.session_state[chave] = valor.copy() if isinstance(valor, (list, dict)) else valor


def etapa() -> str:
    return st.session_state.etapa


def iniciar_revisao(entrada: dict, analise: dict) -> None:
    st.session_state.entrada_atual = entrada
    st.session_state.analise_atual = analise
    st.session_state.etapa = REVISAO


def voltar_para_edicao() -> None:
    """Volta ao formulário mantendo o texto digitado."""
    st.session_state.analise_atual = None
    st.session_state.etapa = FORMULARIO


def concluir(relato: dict, analise: dict) -> None:
    item = {
        **relato,
        "orientacoes_cidadao": analise.get("orientacoes_cidadao", []),
        "analise_id": analise["analise_id"],  # comprovante para avaliar; fica só nesta sessão
        "registrado_nesta_sessao_em": datetime.now().isoformat(timespec="seconds"),
    }
    st.session_state.historico.insert(0, item)
    st.session_state.relato_confirmado = item
    st.session_state.analise_atual = None
    st.session_state.etapa = CONCLUIDO


def novo_relato() -> None:
    st.session_state.etapa = FORMULARIO
    st.session_state.analise_atual = None
    st.session_state.entrada_atual = None
    st.session_state.relato_confirmado = None
    st.session_state.campo_descricao = ""
    st.session_state.campo_bairro = None
    st.session_state.campo_referencia = ""


def preencher_exemplo(descricao: str, bairro: str, referencia: str) -> None:
    st.session_state.campo_descricao = descricao
    st.session_state.campo_bairro = bairro
    st.session_state.campo_referencia = referencia


def historico() -> list[dict]:
    return st.session_state.historico


def atualizar_no_historico(relato: dict) -> None:
    for i, item in enumerate(st.session_state.historico):
        if item["protocolo"] == relato["protocolo"]:
            st.session_state.historico[i] = {**item, **relato}


def comprovante_de(protocolo: str) -> str | None:
    return next((r.get("analise_id") for r in st.session_state.historico if r["protocolo"] == protocolo), None)


def registrar_feedback(protocolo: str, avaliacao: str) -> None:
    st.session_state.feedbacks[protocolo] = avaliacao


def feedback_de(protocolo: str) -> str | None:
    return st.session_state.feedbacks.get(protocolo)
