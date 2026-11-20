"""Erros de domínio e handlers HTTP.

Princípio: o cidadão recebe sempre uma mensagem clara, em linguagem simples,
e um código estável. Detalhes técnicos ficam apenas no log do servidor.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("zelo")


class ErroZelo(Exception):
    status_code = 500
    codigo = "ERRO_INTERNO"
    mensagem = "Algo deu errado do nosso lado. Tente novamente em instantes."

    def __init__(self, mensagem: str | None = None, detalhe_tecnico: str | None = None):
        self.mensagem = mensagem or self.mensagem
        self.detalhe_tecnico = detalhe_tecnico
        super().__init__(self.mensagem)


class ErroIAIndisponivel(ErroZelo):
    status_code = 503
    codigo = "IA_INDISPONIVEL"
    mensagem = "Nosso assistente de análise está indisponível no momento. Tente novamente em alguns minutos."


class ErroIATimeout(ErroZelo):
    status_code = 504
    codigo = "IA_TIMEOUT"
    mensagem = "A análise demorou mais do que o esperado. Tente novamente."


class ErroRespostaIA(ErroZelo):
    status_code = 502
    codigo = "IA_RESPOSTA_INVALIDA"
    mensagem = "Não conseguimos interpretar a análise do seu relato. Tente reformular a descrição."


class ErroEntradaInvalida(ErroZelo):
    status_code = 422
    codigo = "ENTRADA_INVALIDA"
    mensagem = "Alguns campos precisam de ajuste."


class ErroNaoEncontrado(ErroZelo):
    status_code = 404
    codigo = "NAO_ENCONTRADO"
    mensagem = "Não encontramos esse registro."


class ErroConflito(ErroZelo):
    status_code = 409
    codigo = "CONFLITO"
    mensagem = "Esse relato já foi confirmado anteriormente."


class ErroNaoAutorizado(ErroZelo):
    status_code = 401
    codigo = "NAO_AUTORIZADO"
    mensagem = "Acesso restrito à equipe de gestão."


class ErroLimiteRequisicoes(ErroZelo):
    status_code = 429
    codigo = "LIMITE_EXCEDIDO"
    mensagem = "Você enviou muitos relatos em pouco tempo. Aguarde um minuto e tente de novo."


def _corpo(codigo: str, mensagem: str, campos: dict | None = None) -> dict:
    corpo = {"erro": {"codigo": codigo, "mensagem": mensagem}}
    if campos:
        corpo["erro"]["campos"] = campos
    return corpo


_NOMES_CAMPOS = {
    "descricao": "Descrição",
    "bairro": "Bairro",
    "referencia": "Ponto de referência",
    "avaliacao": "Avaliação",
    "comentario": "Comentário",
    "status": "Situação",
}


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ErroZelo)
    async def _erro_zelo(_: Request, exc: ErroZelo):
        if exc.detalhe_tecnico:
            log.warning("%s: %s", exc.codigo, exc.detalhe_tecnico)
        return JSONResponse(status_code=exc.status_code, content=_corpo(exc.codigo, exc.mensagem))

    @app.exception_handler(RequestValidationError)
    async def _erro_validacao(_: Request, exc: RequestValidationError):
        campos: dict[str, str] = {}
        for e in exc.errors():
            nome = str(e["loc"][-1]) if e.get("loc") else "entrada"
            campos[_NOMES_CAMPOS.get(nome, nome)] = e.get("msg", "valor inválido")
        return JSONResponse(
            status_code=422,
            content=_corpo("ENTRADA_INVALIDA", "Alguns campos precisam de ajuste.", campos),
        )

    @app.exception_handler(Exception)
    async def _erro_generico(_: Request, exc: Exception):
        log.exception("Erro não tratado: %s", exc)
        return JSONResponse(status_code=500, content=_corpo(ErroZelo.codigo, ErroZelo.mensagem))
