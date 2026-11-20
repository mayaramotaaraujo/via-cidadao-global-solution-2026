"""LGPD: minimização e mascaramento de dados pessoais.

- `anonimizar` remove CPF, telefone, e-mail e placa do TEXTO do relato antes de
  ele ser classificado, salvo no banco ou escrito em qualquer planilha/e-mail.
- `mascarar_email` é usado nos logs: o log nunca mostra o e-mail completo.
- `FiltroPII` é um filtro de logging que aplica as mesmas máscaras em qualquer
  mensagem de log, como última barreira caso alguém logue um dado sem querer.
"""

from __future__ import annotations

import hashlib
import logging
import re

_PADROES: list[tuple[str, str, re.Pattern]] = [
    ("e-mail", "[E-MAIL REMOVIDO]", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("CPF", "[CPF REMOVIDO]", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("telefone", "[TELEFONE REMOVIDO]",
     # Exige separador ("98765-4321", "(11) 3333 4444") ou o formato de celular com DDD
     # ("11987654321"), para não confundir datas como 20261118 com telefone.
     re.compile(r"(?<![\d-])(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?9?\d{4}[\s-]\d{4}\b|\b\d{2}9\d{8}\b")),
    ("placa", "[PLACA REMOVIDA]", re.compile(r"\b[A-Z]{3}-?\d[A-Z0-9]\d{2}\b", re.IGNORECASE)),
]

_EMAIL_VALIDO = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def anonimizar(texto: str) -> tuple[str, list[str]]:
    """Retorna (texto_mascarado, tipos_de_dado_removidos)."""
    removidos: list[str] = []
    for nome, mascara, padrao in _PADROES:
        texto, n = padrao.subn(mascara, texto)
        if n:
            removidos.append(nome)
    return texto, removidos


def email_valido(email: str | None) -> bool:
    return bool(email) and bool(_EMAIL_VALIDO.match(email.strip()))


def mascarar_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "(sem e-mail)"
    usuario, dominio = email.split("@", 1)
    return f"{usuario[:1]}***@{dominio}"


def hash_curto(*partes: str) -> str:
    """Hash estável usado como chave de idempotência (não é reversível)."""
    bruto = "|".join(p.strip().lower() for p in partes)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()[:20]


class FiltroPII(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            mensagem = record.getMessage()
        except Exception:  # noqa: BLE001 - nunca derrubar o log
            return True
        mascarada, removidos = anonimizar(mensagem)
        if removidos:
            record.msg, record.args = mascarada, ()
        return True
