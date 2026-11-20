"""Cliente HTTP da API Zelo.

Toda comunicação com o back-end passa por aqui. Erros técnicos (conexão,
timeout, JSON inválido, status HTTP) são convertidos em `ErroAPI`, com uma
mensagem pronta para mostrar ao cidadão, sem jargão e sem stack trace.
"""

from typing import Any

import time

import httpx
import streamlit as st

import config


class ErroAPI(Exception):
    def __init__(self, mensagem: str, codigo: str, campos: dict | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo
        self.campos = campos or {}


_MSG_FORA_DO_AR = "Não conseguimos falar com o serviço agora. Verifique sua internet ou tente de novo em alguns minutos."
_MSG_TIMEOUT = "O serviço está demorando mais que o normal para responder. Tente novamente em instantes."
_MSG_INVALIDA = "Recebemos uma resposta inesperada do serviço. Tente novamente."
_MSG_INICIANDO = (
    "O serviço está iniciando, o que pode levar até 1 minuto na primeira visita. "
    "Aguarde um pouco e tente de novo."
)
# Tempo máximo para a API sair da hibernação (plano gratuito do Render).
TIMEOUT_ACORDAR_S = 60

_CAMPOS_ANALISE = {"analise_id", "categoria", "urgencia", "resumo", "orientacoes_cidadao", "orgao_responsavel"}


class ClienteZelo:
    def __init__(self, base_url: str):
        # Um único httpx.Client reaproveita conexões (keep-alive) entre reruns.
        self._http = httpx.Client(base_url=base_url, timeout=config.TIMEOUT_PADRAO_S)

    def _requisitar(self, metodo: str, caminho: str, timeout: float | None = None, **kwargs) -> Any:
        try:
            r = self._http.request(metodo, caminho, timeout=timeout or config.TIMEOUT_PADRAO_S, **kwargs)
        except httpx.TimeoutException as e:
            raise ErroAPI(_MSG_TIMEOUT, "TIMEOUT") from e
        except httpx.HTTPError as e:
            raise ErroAPI(_MSG_FORA_DO_AR, "API_FORA_DO_AR") from e

        try:
            corpo = r.json()
        except ValueError as e:
            # A plataforma devolve uma página HTML (502/503/504) enquanto a API acorda.
            if r.status_code in (502, 503, 504):
                raise ErroAPI(_MSG_INICIANDO, "API_INICIANDO") from e
            raise ErroAPI(_MSG_INVALIDA, "RESPOSTA_INVALIDA") from e

        if r.is_error:
            erro = corpo.get("erro", {}) if isinstance(corpo, dict) else {}
            raise ErroAPI(
                erro.get("mensagem", _MSG_INVALIDA),
                erro.get("codigo", f"HTTP_{r.status_code}"),
                erro.get("campos"),
            )
        return corpo

    # ---------------------------------------------------------------- cidadão
    def saude(self) -> dict:
        return self._requisitar("GET", "/health", timeout=5)

    def bairros(self) -> list[dict]:
        # Primeira chamada de uma visita: pode precisar acordar a API.
        return self._requisitar("GET", "/api/v1/bairros", timeout=TIMEOUT_ACORDAR_S)

    def analisar(self, descricao: str, bairro: str, referencia: str | None) -> dict:
        corpo = {"descricao": descricao, "bairro": bairro, "referencia": referencia or None}
        resposta = self._requisitar("POST", "/api/v1/relatos/analisar", json=corpo, timeout=config.TIMEOUT_ANALISE_S)
        # Defesa em profundidade: confere o contrato antes de usar na tela.
        if not isinstance(resposta, dict) or not _CAMPOS_ANALISE.issubset(resposta):
            raise ErroAPI(_MSG_INVALIDA, "RESPOSTA_INVALIDA")
        return resposta

    def confirmar(self, analise_id: str, categoria: str, urgencia: str) -> dict:
        return self._requisitar(
            "POST",
            "/api/v1/relatos",
            json={"analise_id": analise_id, "categoria_final": categoria, "urgencia_final": urgencia},
        )

    def listar_relatos(self, incluir_simulados: bool = True, dias: int | None = None) -> list[dict]:
        params: dict = {"incluir_simulados": incluir_simulados}
        if dias:
            params["dias"] = dias
        return self._requisitar("GET", "/api/v1/relatos", params=params, timeout=TIMEOUT_ACORDAR_S)

    def obter_relato(self, protocolo: str) -> dict:
        return self._requisitar("GET", f"/api/v1/relatos/{protocolo}")

    def enviar_feedback(self, protocolo: str, analise_id: str, avaliacao: str, comentario: str | None = None) -> dict:
        return self._requisitar(
            "POST",
            f"/api/v1/relatos/{protocolo}/feedback",
            json={"analise_id": analise_id, "avaliacao": avaliacao, "comentario": comentario},
        )

    # ----------------------------------------------------------------- gestor
    def gestor_listar(self, token: str) -> list[dict]:
        return self._requisitar("GET", "/api/v1/gestor/relatos", headers={"X-Gestor-Token": token})

    def gestor_atualizar(self, token: str, protocolo: str, status: str, nota: str | None) -> dict:
        return self._requisitar(
            "PATCH",
            f"/api/v1/gestor/relatos/{protocolo}",
            headers={"X-Gestor-Token": token},
            json={"status": status, "nota": nota or None},
        )


@st.cache_resource
def obter_cliente() -> ClienteZelo:
    """Recurso compartilhado (não serializável): criado uma vez por processo."""
    return ClienteZelo(config.API_URL)


# ---------------------------------------------------------------------------
# Leituras cacheadas: evitam chamar a API a cada rerun do Streamlit.
# Exceções NÃO são cacheadas, então uma falha temporária não "gruda".
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def carregar_bairros() -> list[dict]:
    return obter_cliente().bairros()


@st.cache_data(ttl=30, show_spinner=False)
def carregar_relatos_publicos(incluir_simulados: bool) -> list[dict]:
    return obter_cliente().listar_relatos(incluir_simulados=incluir_simulados)


@st.cache_data(ttl=20, show_spinner=False)
def _saude_ok() -> bool:
    # Só o resultado "online" fica em cache. Se falhar, a exceção impede o cache
    # e a próxima interação testa de novo (a API pode ter acabado de acordar).
    if obter_cliente().saude().get("status") != "ok":
        raise ErroAPI(_MSG_FORA_DO_AR, "API_FORA_DO_AR")
    return True


def verificar_saude() -> bool:
    try:
        return _saude_ok()
    except ErroAPI:
        return False


def aguardar_servico(limite_s: float = 90, pausa_s: float = 2) -> bool:
    """Espera a API sair da hibernação (plano gratuito do Render), em vez de mostrar erro.

    Tenta de novo enquanto a plataforma responde "iniciando" (timeout, 502/503/504).
    Se a conexão for recusada de cara, a API está fora do ar de verdade: desiste na hora.
    """
    fim = time.monotonic() + limite_s
    while True:
        try:
            if obter_cliente().saude().get("status") == "ok":
                return True
        except ErroAPI as e:
            if e.codigo == "API_FORA_DO_AR":
                return False
        if time.monotonic() >= fim:
            return False
        time.sleep(pausa_s)
