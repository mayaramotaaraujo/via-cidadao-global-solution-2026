"""Configuração do front-end.

A URL da API vem de variável de ambiente (API_URL) ou de st.secrets.
O front-end NÃO tem e NÃO precisa da chave da OpenAI.
"""

import os

import streamlit as st

try:  # carrega ../.env no desenvolvimento local, se existir
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass


def _ler(chave: str, padrao: str) -> str:
    if chave in os.environ:
        return os.environ[chave]
    try:
        return str(st.secrets[chave])
    except Exception:  # st.secrets lança erro se não houver secrets.toml
        return padrao


API_URL = _ler("API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT_ANALISE_S = float(_ler("TIMEOUT_ANALISE_S", "45"))
TIMEOUT_PADRAO_S = float(_ler("TIMEOUT_PADRAO_S", "10"))
