"""TEMA 2: integração com APIs REST.

1. Open-Meteo (pública, sem chave): previsão de chuva do dia por bairro. Só a
   coordenada do CENTRO do bairro é enviada; nenhum dado do cidadão sai daqui.
2. API do app Zelo (opcional): busca os relatos que entraram pelo app
   (`GET /api/v1/gestor/relatos?status=recebido`, token no cabeçalho).

Toda chamada tem timeout, retry com espera exponencial (1s, 2s, 4s...) e um
caminho seguro: se a API não responder, o robô registra no log e segue.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

log = logging.getLogger("zelo.apis")

# Erros que valem nova tentativa (rede, timeout, 5xx, 429). 4xx de cliente não.
_STATUS_RETENTAVEL = {429, 500, 502, 503, 504}


class FalhaIntegracao(Exception):
    pass


def com_retry(func: Callable[[], Any], nome: str, tentativas: int, espera_base: float) -> Any:
    ultimo: Exception | None = None
    for n in range(1, tentativas + 1):
        try:
            return func()
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            ultimo = e
            if status not in _STATUS_RETENTAVEL:
                log.error("%s: erro HTTP %s (não adianta tentar de novo)", nome, status)
                break
            log.warning("%s: HTTP %s na tentativa %d/%d", nome, status, n, tentativas)
        except (requests.ConnectionError, requests.Timeout) as e:
            ultimo = e
            log.warning("%s: %s na tentativa %d/%d", nome, type(e).__name__, n, tentativas)
        except (ValueError, KeyError, TypeError, IndexError) as e:  # JSON fora do formato
            ultimo = e
            log.error("%s: resposta em formato inesperado (%s)", nome, e)
            break
        if n < tentativas:
            time.sleep(espera_base * 2 ** (n - 1))
    raise FalhaIntegracao(f"{nome} indisponível após {tentativas} tentativa(s): {type(ultimo).__name__}")


@dataclass
class ClimaOpenMeteo:
    url: str
    timeout: float = 5.0
    tentativas: int = 3
    espera_base: float = 1.0
    habilitado: bool = True
    _cache: dict[tuple[float, float], float | None] = field(default_factory=dict)
    chamadas: int = 0
    falhas: int = 0
    circuito_aberto: bool = False

    def chuva_hoje_mm(self, lat: float, lon: float) -> float | None:
        """mm de chuva previstos hoje, ou None se a API estiver indisponível."""
        if not self.habilitado or self.circuito_aberto:
            return None
        chave = (round(lat, 2), round(lon, 2))
        if chave in self._cache:
            return self._cache[chave]

        def chamar() -> float:
            self.chamadas += 1
            r = requests.get(self.url, timeout=self.timeout, params={
                "latitude": lat, "longitude": lon,
                "daily": "precipitation_sum", "forecast_days": 1,
                "timezone": "America/Sao_Paulo",
            })
            r.raise_for_status()
            valor = r.json()["daily"]["precipitation_sum"][0]
            return float(valor or 0.0)

        try:
            mm = com_retry(chamar, "Open-Meteo", self.tentativas, self.espera_base)
        except FalhaIntegracao as e:
            self.falhas += 1
            # Disjuntor: depois de 2 bairros seguidos sem resposta, para de tentar
            # nesta execução para não travar o robô esperando timeouts.
            if self.falhas >= 2:
                self.circuito_aberto = True
                log.error("%s. Seguindo SEM contexto de chuva nesta execução.", e)
            else:
                log.warning("%s. Este bairro fica sem contexto de chuva.", e)
            return None
        self._cache[chave] = mm
        return mm

    @property
    def status(self) -> str:
        if not self.habilitado:
            return "desabilitada"
        if self.circuito_aberto:
            return "indisponível (seguiu sem chuva)"
        if self.falhas:
            return f"parcial ({self.falhas} falha(s))"
        return "ok" if self.chamadas else "não utilizada"


def buscar_relatos_app(base_url: str, token: str, timeout: float, tentativas: int,
                       espera_base: float) -> list[dict]:
    """Relatos novos do app Zelo. Levanta FalhaIntegracao se não conseguir."""
    if not base_url or not token:
        raise FalhaIntegracao("API do app Zelo não configurada (ZELO_API_URL / ZELO_GESTOR_TOKEN)")

    def chamar() -> list[dict]:
        r = requests.get(f"{base_url}/api/v1/gestor/relatos", params={"status": "recebido"},
                         headers={"X-Gestor-Token": token}, timeout=timeout)
        r.raise_for_status()
        dados = r.json()
        if not isinstance(dados, list):
            raise ValueError("a API não devolveu uma lista")
        return dados

    return com_retry(chamar, "API do app Zelo", tentativas, espera_base)
