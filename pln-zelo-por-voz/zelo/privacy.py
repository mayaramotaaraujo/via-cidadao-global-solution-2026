"""Cuidados de LGPD e segurança.

- CONSENT_TEXT: aviso exibido antes do primeiro uso.
- mask_pii: remove CPF, RG, telefone, e-mail e CEP do texto antes de ele ir
  para a API do LLM e para o histórico (minimização de dados).
- secure_delete: apaga o arquivo de áudio logo após a transcrição.
- detect_emergency: sinaliza falas com possível risco à vida.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

CONSENT_TEXT = """### Antes de começar: como o Zelo trata a sua voz

- **A conversa é gravada e processada.** Sua fala é gravada apenas pelo tempo necessário para virar texto.
- **O áudio fica no seu computador.** A transcrição é feita localmente (Whisper) e o arquivo de áudio é **apagado logo em seguida**.
- **O que vai para a nuvem:** apenas o **texto** da pergunta, com CPF, RG, telefone, e-mail e CEP **mascarados**, é enviado à API da OpenAI para gerar a resposta. O texto da resposta é enviado ao serviço de voz da Microsoft (edge-tts) para virar áudio.
- **Nada é guardado:** o Zelo não armazena gravações nem o texto das conversas. Só registra tempos de processamento (latência), sem conteúdo.
- **Limites:** o Zelo orienta sobre zeladoria urbana. Ele não substitui médico, advogado ou serviço de emergência. **Em emergência ligue 193 (Bombeiros), 199 (Defesa Civil), 192 (SAMU) ou 190 (Polícia).**
- Você pode limpar a conversa a qualquer momento no botão "Nova conversa".
"""

_PATTERNS = [
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    (re.compile(r"\b\d{5}-?\d{3}\b"), "[CEP]"),
    (re.compile(r"(?:\(?\b\d{2}\)?\s?)?\b9?\d{4}[-\s]?\d{4}\b"), "[TELEFONE]"),
    (re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}-?[\dxX]\b"), "[RG]"),
]


def mask_pii(text: str) -> str:
    for pattern, token in _PATTERNS:
        text = pattern.sub(token, text)
    return text


def secure_delete(path: str | os.PathLike | None) -> bool:
    """Sobrescreve com zeros e apaga o arquivo de áudio. Retorna True se apagou."""
    if not path:
        return False
    p = Path(path)
    try:
        if p.is_file():
            size = p.stat().st_size
            with open(p, "r+b") as fh:
                fh.write(b"\x00" * size)
            p.unlink()
            return True
    except OSError:
        pass
    return False


_EMERGENCY = re.compile(
    r"\b(inc[eê]ndio|fogo|desab|desmoron|deslizamento|soterr|ferid[oa]|sangr|desmai|"
    r"fa[ií]sca|choque el[eé]trico|fio (?:ca[ií]do|partido|solto)|correnteza|"
    r"arrastad[oa]|preso na [aá]gua|socorro|emerg[eê]ncia|infarto|dor no peito|falta de ar|n[aã]o (?:est[aá] )?respira)"
    ,
    re.IGNORECASE,
)


def detect_emergency(text: str) -> bool:
    return bool(_EMERGENCY.search(text or ""))


_HEALTH = re.compile(r"dor no peito|falta de ar|infarto|desmai|n[aã]o (?:est[aá] )?respira|sangr|ferid[oa]", re.IGNORECASE)
_EMERGENCY_NUMBERS = re.compile(r"\b19[0-3]\b|\b199\b")


def ensure_emergency_number(user_text: str, answer: str) -> str:
    """Garantia determinística: se a fala indica emergência e o LLM não citou
    nenhum número de emergência, o número certo é colocado no início."""
    if not detect_emergency(user_text) or _EMERGENCY_NUMBERS.search(answer or ""):
        return answer
    if _HEALTH.search(user_text or ""):
        prefix = "Se for uma emergência, ligue agora para o SAMU no 192."
    else:
        prefix = "Se houver risco, ligue agora para os Bombeiros no 193 ou para a Defesa Civil no 199."
    return f"{prefix} {answer}".strip()
