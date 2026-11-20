"""LGPD: remoção de dados pessoais ANTES de o texto sair do nosso servidor.

O relato do cidadão pode conter CPF, telefone, e-mail ou placa de carro
("meu telefone é..."). Nada disso é necessário para classificar um buraco,
então mascaramos antes de enviar ao LLM e antes de salvar no banco
(princípio da minimização de dados, art. 6º, III da LGPD).
"""

import re

_PADROES: list[tuple[str, str, re.Pattern]] = [
    ("e-mail", "[E-MAIL REMOVIDO]", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("CPF", "[CPF REMOVIDO]", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    (
        "telefone",
        "[TELEFONE REMOVIDO]",
        re.compile(r"(?:\+?55\s?)?(?:\(?\d{2}\)?[\s-]?)?9?\d{4}[\s-]?\d{4}\b"),
    ),
    ("placa de veículo", "[PLACA REMOVIDA]", re.compile(r"\b[A-Z]{3}-?\d[A-Z0-9]\d{2}\b", re.IGNORECASE)),
]


def anonimizar(texto: str) -> tuple[str, list[str]]:
    """Retorna (texto_mascarado, tipos_de_dado_removidos)."""
    removidos: list[str] = []
    for nome, mascara, padrao in _PADROES:
        texto, n = padrao.subn(mascara, texto)
        if n:
            removidos.append(nome)
    return texto, removidos
