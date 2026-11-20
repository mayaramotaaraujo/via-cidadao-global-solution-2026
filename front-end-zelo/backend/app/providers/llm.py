"""Acesso ao modelo de linguagem (LLM).

Este é o ÚNICO lugar do sistema que conversa com o provedor de IA.
O front-end nunca chama a OpenAI diretamente e nunca vê a chave de API.
"""

import logging
from typing import Protocol

import openai
from pydantic import ValidationError

from app.core.erros import ErroIAIndisponivel, ErroIATimeout, ErroRespostaIA
from app.schemas.relato import AnaliseLLM, Categoria, Urgencia

log = logging.getLogger("zelo.llm")


class ProvedorLLM(Protocol):
    nome_modelo: str

    def analisar(self, instrucoes: str, conteudo: str) -> AnaliseLLM: ...


class OpenAIProvedor:
    """Usa Structured Outputs: a resposta é validada contra o schema Pydantic
    `AnaliseLLM`. Se a IA devolver algo fora do contrato, a chamada falha
    e tratamos como resposta inválida (nunca repassamos texto solto)."""

    def __init__(self, api_key: str, modelo: str, timeout: float):
        self.nome_modelo = modelo
        # max_retries=1: uma nova tentativa automática em falhas transitórias,
        # sem deixar o cidadão esperando demais.
        self._cliente = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=1)

    def _parametros_extras(self) -> dict:
        # Modelos de raciocínio (gpt-5.x, o-series) aceitam "reasoning";
        # esforço baixo = menor latência, suficiente para classificação.
        if self.nome_modelo.startswith(("gpt-5", "o1", "o3", "o4")):
            return {"reasoning": {"effort": "low"}}
        return {"temperature": 0.2}

    def analisar(self, instrucoes: str, conteudo: str) -> AnaliseLLM:
        try:
            resposta = self._cliente.responses.parse(
                model=self.nome_modelo,
                instructions=instrucoes,
                input=conteudo,
                text_format=AnaliseLLM,
                max_output_tokens=2000,
                store=False,  # não guardar o relato do cidadão no provedor
                **self._parametros_extras(),
            )
        except openai.APITimeoutError as e:
            raise ErroIATimeout(detalhe_tecnico=str(e)) from e
        except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
            raise ErroIAIndisponivel(detalhe_tecnico=f"credencial inválida: {e}") from e
        except (openai.RateLimitError, openai.APIConnectionError, openai.InternalServerError) as e:
            raise ErroIAIndisponivel(detalhe_tecnico=str(e)) from e
        except (openai.LengthFinishReasonError, openai.ContentFilterFinishReasonError, ValidationError) as e:
            raise ErroRespostaIA(detalhe_tecnico=str(e)) from e
        except openai.APIStatusError as e:
            raise ErroIAIndisponivel(detalhe_tecnico=f"status {e.status_code}: {e}") from e

        analise = resposta.output_parsed
        if analise is None:  # recusa do modelo ou saída vazia
            raise ErroRespostaIA(detalhe_tecnico="output_parsed vazio (possível recusa)")
        return analise


class FakeProvedor:
    """Provedor determinístico por palavras-chave.

    NÃO é a IA do produto: existe para os testes automatizados (pytest)
    rodarem sem internet e sem custo, e para desenvolver a interface offline.
    Ativado apenas com LLM_PROVIDER=fake.
    """

    nome_modelo = "fake-palavras-chave"

    _REGRAS = [
        (("buraco", "cratera", "asfalto"), Categoria.BURACO),
        (("poste", "lâmpada", "lampada", "escuro", "iluminação"), Categoria.ILUMINACAO),
        (("calçada", "calcada", "cadeirante", "rampa"), Categoria.CALCADA),
        (("alag", "enchente", "bueiro", "boca de lobo"), Categoria.ALAGAMENTO),
        (("lixo", "entulho", "descarte"), Categoria.LIXO),
        (("árvore", "arvore", "galho", "poda"), Categoria.ARVORE),
        (("semáforo", "semaforo", "placa", "faixa"), Categoria.SINALIZACAO),
    ]

    def analisar(self, instrucoes: str, conteudo: str) -> AnaliseLLM:
        texto = conteudo.lower()
        categoria = next(
            (cat for chaves, cat in self._REGRAS if any(c in texto for c in chaves)),
            Categoria.OUTROS,
        )
        risco = any(p in texto for p in ("fio", "choque", "caindo", "desabando", "ilhad"))
        urgencia = Urgencia.CRITICA if risco else Urgencia.MEDIA
        return AnaliseLLM(
            categoria=categoria,
            urgencia=urgencia,
            justificativa_urgencia="Classificação simulada por palavras-chave.",
            resumo=f"Relato de {categoria.value.replace('_', ' ')}.",
            orientacoes_cidadao=["Mantenha distância do local.", "Acompanhe pelo número de protocolo."],
            risco_imediato=risco,
            fora_do_escopo=categoria == Categoria.OUTROS,
            confianca=0.9 if categoria != Categoria.OUTROS else 0.4,
        )
