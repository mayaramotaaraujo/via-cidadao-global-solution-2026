"""Módulo LLM. Provedores intercambiáveis com a mesma interface `chat(messages)`.

- OpenAIProvider: padrão (gpt-4o-mini), baixa latência e bom português.
- OllamaProvider: alternativa 100% local (ex.: qwen2.5:3b), útil sem internet
  ou para a comparação entre modelos.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests

from .config import settings


@dataclass
class LLMResult:
    text: str
    elapsed_s: float
    model: str
    model_version: str = ""


class OpenAIProvider:
    def __init__(self, model: str | None = None, temperature: float | None = None, max_tokens: int | None = None):
        from openai import OpenAI

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY não definida. Copie .env.example para .env e preencha a chave.")
        self.client = OpenAI()
        self.model = model or settings.llm_model
        self.temperature = settings.llm_temperature if temperature is None else temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens

    @property
    def name(self) -> str:
        return f"openai:{self.model}"

    def chat(self, messages: list[dict]) -> LLMResult:
        t0 = time.perf_counter()
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return LLMResult(resp.choices[0].message.content.strip(), time.perf_counter() - t0, self.name, resp.model)


class OllamaProvider:
    def __init__(self, model: str | None = None, temperature: float | None = None, max_tokens: int | None = None):
        self.model = model or "qwen2.5:3b"
        self.temperature = settings.llm_temperature if temperature is None else temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.url = settings.ollama_url.rstrip("/") + "/api/chat"

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def chat(self, messages: list[dict]) -> LLMResult:
        t0 = time.perf_counter()
        r = requests.post(
            self.url,
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
            },
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()
        return LLMResult(data["message"]["content"].strip(), time.perf_counter() - t0, self.name, data.get("model", self.model))


def build_llm(provider: str | None = None, model: str | None = None):
    provider = (provider or settings.llm_provider).lower()
    if provider == "openai":
        return OpenAIProvider(model=model)
    if provider == "ollama":
        return OllamaProvider(model=model)
    raise ValueError(f"Provedor de LLM desconhecido: {provider}")
