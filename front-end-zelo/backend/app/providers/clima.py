"""Dados abertos: previsão de chuva via Open-Meteo (API pública, sem chave).

Cruzamos o relato do cidadão com a previsão do tempo da região: um bueiro
entupido num dia de 40 mm de chuva é mais urgente do que num dia seco.

Robustez: se a API pública falhar ou demorar, a análise segue SEM o
contexto climático (degradação graciosa) — o cidadão nunca fica sem resposta
por causa de uma fonte auxiliar.
"""

import logging
import time

import httpx

from app.schemas.relato import ContextoClima

log = logging.getLogger("zelo.clima")

URL = "https://api.open-meteo.com/v1/forecast"
_TTL_SEGUNDOS = 30 * 60


class ClimaProvedor:
    def __init__(self, timeout: float = 3.0, habilitado: bool = True):
        self._timeout = timeout
        self._habilitado = habilitado
        self._cache: dict[tuple[float, float], tuple[float, ContextoClima]] = {}

    def previsao_hoje(self, lat: float, lon: float) -> ContextoClima | None:
        if not self._habilitado:
            return None
        chave = (round(lat, 2), round(lon, 2))
        em_cache = self._cache.get(chave)
        if em_cache and time.monotonic() - em_cache[0] < _TTL_SEGUNDOS:
            return em_cache[1]
        try:
            r = httpx.get(
                URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "precipitation_sum,precipitation_probability_max",
                    "forecast_days": 1,
                    "timezone": "America/Sao_Paulo",
                },
                timeout=self._timeout,
            )
            r.raise_for_status()
            diario = r.json()["daily"]
            contexto = ContextoClima(
                chuva_prevista_mm=float(diario["precipitation_sum"][0] or 0.0),
                probabilidade_chuva=diario.get("precipitation_probability_max", [None])[0],
            )
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
            log.info("Open-Meteo indisponível, seguindo sem clima: %s", e)
            return None
        self._cache[chave] = (time.monotonic(), contexto)
        return contexto
