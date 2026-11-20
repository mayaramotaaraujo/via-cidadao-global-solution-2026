"""Configuração central do back-end.

Todos os valores vêm de variáveis de ambiente (ou de um arquivo .env local,
que NUNCA é versionado). Veja o arquivo .env.example na raiz do projeto.
"""

from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


TOKENS_INSEGUROS = {"", "troque-este-token", "troque-por-um-codigo-forte"}


class Configuracoes(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- IA ---------------------------------------------------------------
    # "openai" em produção. "fake" é um provedor determinístico usado apenas
    # em testes automatizados e para desenvolver sem gastar créditos.
    llm_provider: str = Field(default="openai")
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.4-mini"
    llm_timeout_segundos: float = 30.0

    # --- Segurança ----------------------------------------------------------
    # Lista separada por vírgulas. Nunca usar "*" em produção.
    allowed_origins: str = "http://localhost:8501"
    gestor_token: SecretStr = SecretStr("troque-este-token")
    limite_analises_por_minuto: int = 8
    # Quantos proxies confiáveis existem na frente da API (0 = nenhum: usa o IP
    # da conexão). No Render, 1. Opcional: REDES_PROXY restringe de quais redes
    # (CIDR, separadas por vírgula) o X-Forwarded-For é aceito.
    proxies_confiaveis: int = Field(default=0, ge=0, le=5)
    redes_proxy: str = ""

    # --- Dados ----------------------------------------------------------------
    db_path: str = "data/zelo.db"
    seed_demo: bool = True  # popula o painel com relatos SIMULADOS (marcados como tal)
    clima_habilitado: bool = True
    clima_timeout_segundos: float = 3.0

    ambiente: str = "desenvolvimento"

    @model_validator(mode="after")
    def _exigir_token_forte_em_producao(self) -> "Configuracoes":
        # Fail-closed: em produção a API não sobe com o token de exemplo ou fraco.
        token = self.gestor_token.get_secret_value()
        if self.ambiente == "producao" and (token in TOKENS_INSEGUROS or len(token) < 16):
            raise ValueError("GESTOR_TOKEN ausente ou fraco: defina um código com 16+ caracteres em produção.")
        return self

    @property
    def redes_proxy_lista(self) -> list:
        import ipaddress

        return [ipaddress.ip_network(r.strip(), strict=False) for r in self.redes_proxy.split(",") if r.strip()]

    @property
    def origens_permitidas(self) -> list[str]:
        origens = [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        # Defesa extra: mesmo se alguém configurar "*", ignoramos em produção.
        if self.ambiente == "producao":
            origens = [o for o in origens if o != "*"]
        return origens


@lru_cache
def obter_configuracoes() -> Configuracoes:
    return Configuracoes()
