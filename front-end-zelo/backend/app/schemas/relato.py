"""Modelos Pydantic de entrada e saída da API.

Separação importante:
- `AnaliseLLM` é o contrato que o modelo de IA é OBRIGADO a seguir
  (Structured Outputs da OpenAI). Contém só o que exige interpretação de texto.
- `AnaliseResposta` é o que a API devolve ao front-end: a saída da IA
  enriquecida com regras determinísticas (órgão responsável, prazo,
  revisão humana), que não deixamos a IA "inventar".
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Categoria(str, Enum):
    BURACO = "buraco_pavimentacao"
    ILUMINACAO = "iluminacao_publica"
    CALCADA = "calcada_acessibilidade"
    ALAGAMENTO = "alagamento_drenagem"
    LIXO = "lixo_entulho"
    ARVORE = "arvore_poda"
    SINALIZACAO = "sinalizacao_transito"
    OUTROS = "outros"


class Urgencia(str, Enum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"

    @property
    def nivel(self) -> int:
        return ["baixa", "media", "alta", "critica"].index(self.value)

    @classmethod
    def de_nivel(cls, nivel: int) -> "Urgencia":
        ordem = [cls.BAIXA, cls.MEDIA, cls.ALTA, cls.CRITICA]
        return ordem[max(0, min(nivel, 3))]


class Status(str, Enum):
    RECEBIDO = "recebido"
    EM_ANALISE = "em_analise"
    ENCAMINHADO = "encaminhado"
    RESOLVIDO = "resolvido"
    REJEITADO = "rejeitado"


# --------------------------------------------------------------------------
# Entrada do cidadão
# --------------------------------------------------------------------------
class RelatoEntrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    descricao: str = Field(min_length=20, max_length=1000, description="Relato livre do cidadão")
    bairro: str = Field(min_length=2, max_length=60)
    referencia: str | None = Field(default=None, max_length=150)

    @field_validator("descricao")
    @classmethod
    def _descricao_minima(cls, v: str) -> str:
        if len(v.split()) < 4:
            raise ValueError("descreva o problema com pelo menos 4 palavras")
        return v

    @field_validator("referencia")
    @classmethod
    def _referencia_vazia(cls, v: str | None) -> str | None:
        return v or None


# --------------------------------------------------------------------------
# Contrato com o LLM (Structured Outputs)
# --------------------------------------------------------------------------
class AnaliseLLM(BaseModel):
    categoria: Categoria = Field(description="Categoria do problema de zeladoria")
    urgencia: Urgencia = Field(description="Nível de urgência segundo os critérios do sistema")
    justificativa_urgencia: str = Field(description="Uma frase simples explicando a urgência")
    resumo: str = Field(description="Resumo objetivo em até 20 palavras, sem dados pessoais")
    orientacoes_cidadao: list[str] = Field(description="De 2 a 4 orientações práticas e curtas")
    risco_imediato: bool = Field(description="True se há risco imediato à vida ou à integridade física")
    fora_do_escopo: bool = Field(description="True se o relato não é um problema de zeladoria urbana")
    confianca: float = Field(description="Confiança da classificação, de 0.0 a 1.0")


# --------------------------------------------------------------------------
# Saída da API
# --------------------------------------------------------------------------
class ContextoClima(BaseModel):
    chuva_prevista_mm: float
    probabilidade_chuva: int | None = None
    fonte: str = "Open-Meteo"


class AnaliseResposta(BaseModel):
    analise_id: str
    categoria: Categoria
    urgencia: Urgencia
    justificativa_urgencia: str
    resumo: str
    orientacoes_cidadao: list[str]
    orgao_responsavel: str
    prazo_estimado_dias: int
    risco_imediato: bool
    fora_do_escopo: bool
    confianca: float = Field(ge=0, le=1)
    precisa_revisao_humana: bool
    motivos_revisao: list[str] = []
    ajustes_por_regra: list[str] = []
    dados_pessoais_removidos: list[str] = []
    contexto_clima: ContextoClima | None = None
    modelo: str
    versao_prompt: str
    latencia_ms: int


class ConfirmacaoRelato(BaseModel):
    """Human-in-the-loop: o cidadão confirma ou corrige a análise da IA."""

    model_config = ConfigDict(extra="forbid")

    analise_id: str = Field(min_length=8, max_length=64)
    categoria_final: Categoria
    urgencia_final: Urgencia


class RelatoPublico(BaseModel):
    """O que qualquer pessoa pode ver no painel: sem texto livre do cidadão."""

    protocolo: str
    criado_em: datetime
    atualizado_em: datetime
    bairro: str
    latitude: float
    longitude: float
    categoria: Categoria
    urgencia: Urgencia
    status: Status
    resumo: str
    orgao_responsavel: str
    prazo_estimado_dias: int
    ia_corrigida: bool
    feedback: Literal["util", "incorreto"] | None = None
    simulado: bool = False


class RelatoGestor(RelatoPublico):
    descricao_anonimizada: str
    categoria_ia: Categoria
    urgencia_ia: Urgencia
    confianca_ia: float
    nota_gestor: str | None = None
    feedback_comentario: str | None = None


class FeedbackEntrada(BaseModel):
    """`analise_id` funciona como comprovante: só quem fez o relato o possui
    (128 bits aleatórios, nunca exibido no painel público)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    analise_id: str = Field(min_length=8, max_length=64)
    avaliacao: Literal["util", "incorreto"]
    comentario: str | None = Field(default=None, max_length=300)


class AtualizacaoStatus(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    status: Status
    nota: str | None = Field(default=None, max_length=300)


class Bairro(BaseModel):
    nome: str
    zona: str
