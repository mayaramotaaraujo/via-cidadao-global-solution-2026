"""Configuração central do robô.

Tudo que é segredo (senha SMTP, token do gestor do app Zelo) vem de variáveis
de ambiente carregadas do arquivo .env, que NÃO vai para o repositório.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv é opcional: sem ele, valem só as variáveis do sistema
    def load_dotenv(*_a, **_k):
        return False

RAIZ = Path(__file__).resolve().parent.parent


def _bool(valor: str | None, padrao: bool = False) -> bool:
    if valor is None or valor == "":
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


@dataclass
class Config:
    # Pastas
    pasta_entrada: Path = RAIZ / "entrada"
    pasta_saida: Path = RAIZ / "saida"
    pasta_logs: Path = RAIZ / "logs"
    caminho_banco: Path = RAIZ / "dados" / "zelo_robo.db"
    caminho_modelo: Path = RAIZ / "modelos" / "classificador.joblib"
    caminho_treino: Path = RAIZ / "dados" / "treino" / "relatos_rotulados.csv"

    # IA
    limiar_confianca: float = 0.55
    limiar_chuva_forte_mm: float = 20.0

    # Open-Meteo (API pública, sem chave)
    clima_habilitado: bool = True
    clima_url: str = "https://api.open-meteo.com/v1/forecast"
    clima_timeout_s: float = 5.0
    clima_tentativas: int = 3

    # API do app Zelo (opcional). Sem URL/token, o robô usa o arquivo exportado.
    zelo_api_url: str = ""
    zelo_gestor_token: str = field(default="", repr=False)
    zelo_api_timeout_s: float = 20.0  # o Render gratuito pode demorar para "acordar"

    # E-mail
    email_modo: str = "arquivo"  # "arquivo" (salva .eml) ou "smtp" (envia de verdade)
    smtp_host: str = ""
    smtp_porta: int = 587
    smtp_usuario: str = ""
    smtp_senha: str = field(default="", repr=False)
    smtp_remetente: str = "robo.zelo@example.com"
    smtp_tls: bool = True
    smtp_timeout_s: float = 10.0
    smtp_tentativas: int = 3
    email_coordenacao: str = "coordenacao.zeladoria@example.com"

    # Nível de log no terminal (o arquivo logs/robo.log sempre recebe tudo)
    nivel_log_console: int = 20  # 20 = INFO

    # Espera base do retry (segundos). Os testes usam 0 para rodar rápido.
    espera_retry_s: float = 1.0

    @classmethod
    def carregar(cls, **sobrescritas) -> "Config":
        load_dotenv(RAIZ / ".env")
        env = os.environ.get
        cfg = cls(
            clima_habilitado=_bool(env("CLIMA_HABILITADO"), True),
            clima_url=env("CLIMA_URL") or cls.clima_url,
            zelo_api_url=(env("ZELO_API_URL") or "").rstrip("/"),
            zelo_gestor_token=env("ZELO_GESTOR_TOKEN") or "",
            email_modo=(env("EMAIL_MODO") or "arquivo").lower(),
            smtp_host=env("SMTP_HOST") or "",
            smtp_porta=int(env("SMTP_PORTA") or 587),
            smtp_usuario=env("SMTP_USUARIO") or "",
            smtp_senha=env("SMTP_SENHA") or "",
            smtp_remetente=env("SMTP_REMETENTE") or cls.smtp_remetente,
            smtp_tls=_bool(env("SMTP_TLS"), True),
            email_coordenacao=env("EMAIL_COORDENACAO") or cls.email_coordenacao,
        )
        for chave, valor in sobrescritas.items():
            setattr(cfg, chave, valor)
        return cfg

    def garantir_pastas(self) -> None:
        for p in (self.pasta_entrada, self.pasta_saida, self.pasta_logs,
                  self.caminho_banco.parent, self.caminho_modelo.parent):
            p.mkdir(parents=True, exist_ok=True)
