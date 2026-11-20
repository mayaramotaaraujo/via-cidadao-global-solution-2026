"""Injeção de dependências (FastAPI `Depends`).

Os routers recebem provedores prontos, sem saber como foram criados.
Nos testes, trocamos o LLM real por um falso via `app.dependency_overrides`.
"""

import ipaddress
import secrets
import time
from collections import OrderedDict, deque
from functools import lru_cache

from fastapi import Depends, Header, Request

from app.core.config import Configuracoes, obter_configuracoes
from app.core.erros import ErroIAIndisponivel, ErroLimiteRequisicoes, ErroNaoAutorizado
from app.providers.clima import ClimaProvedor
from app.providers.llm import FakeProvedor, OpenAIProvedor, ProvedorLLM
from app.providers.repositorio import Repositorio


@lru_cache
def obter_llm() -> ProvedorLLM:
    cfg = obter_configuracoes()
    if cfg.llm_provider == "fake":
        return FakeProvedor()
    if not cfg.openai_api_key:
        raise ErroIAIndisponivel(detalhe_tecnico="OPENAI_API_KEY não configurada")
    return OpenAIProvedor(cfg.openai_api_key.get_secret_value(), cfg.openai_model, cfg.llm_timeout_segundos)


@lru_cache
def obter_clima() -> ClimaProvedor:
    cfg = obter_configuracoes()
    return ClimaProvedor(timeout=cfg.clima_timeout_segundos, habilitado=cfg.clima_habilitado)


@lru_cache
def obter_repositorio() -> Repositorio:
    cfg = obter_configuracoes()
    repo = Repositorio(cfg.db_path)
    if cfg.seed_demo:
        repo.popular_demo()
    return repo


def exigir_gestor(
    x_gestor_token: str | None = Header(default=None),
    cfg: Configuracoes = Depends(obter_configuracoes),
) -> None:
    """RBAC simples: rotas de gestão exigem o token da equipe no cabeçalho."""
    esperado = cfg.gestor_token.get_secret_value()
    if not x_gestor_token or not secrets.compare_digest(x_gestor_token, esperado):
        raise ErroNaoAutorizado()


def ip_do_cliente(request: Request, cfg) -> str:
    """IP real do cidadão.

    Atrás de proxy (Render), request.client.host é o IP do proxy. Cada proxy
    ACRESCENTA ao final do X-Forwarded-For o IP que viu; tudo antes disso pode
    ter sido escrito pelo próprio cliente. Por isso:
    - juntamos TODAS as linhas do cabeçalho (o cliente pode mandar a sua);
    - pegamos a entrada N posições a partir da direita (N = PROXIES_CONFIAVEIS);
    - se REDES_PROXY estiver configurado, só confiamos no cabeçalho quando a
      conexão vem de uma dessas redes.
    """
    direto = request.client.host if request.client else "desconhecido"
    saltos = getattr(cfg, "proxies_confiaveis", 0)
    if saltos <= 0:
        return direto
    redes = getattr(cfg, "redes_proxy_lista", [])
    if redes:
        try:
            if not any(ipaddress.ip_address(direto) in rede for rede in redes):
                return direto
        except ValueError:
            return direto
    entradas = [
        e.strip()
        for linha in request.headers.getlist("x-forwarded-for")
        for e in linha.split(",")
        if e.strip()
    ]
    if len(entradas) < saltos:
        return direto
    candidato = entradas[-saltos]
    try:
        return str(ipaddress.ip_address(candidato))
    except ValueError:  # valor malformado: não usar como chave
        return direto


class LimitadorTaxa:
    """Limite de análises por IP por minuto: protege contra uso indevido
    (spam de relatos) e contra custo descontrolado de chamadas ao LLM."""

    MAX_IPS = 10_000  # teto rígido de memória (LRU)

    def __init__(self, max_ips: int = MAX_IPS):
        self._max_ips = max_ips
        self._historico: OrderedDict[str, deque] = OrderedDict()

    def __call__(self, request: Request, cfg: Configuracoes = Depends(obter_configuracoes)) -> None:
        ip = ip_do_cliente(request, cfg)
        agora = time.monotonic()
        fila = self._historico.get(ip)
        if fila is None:
            fila = self._historico[ip] = deque()
            # O(1): descarta o IP usado há mais tempo quando passa do teto.
            if len(self._historico) > self._max_ips:
                self._historico.popitem(last=False)
        else:
            self._historico.move_to_end(ip)
        while fila and agora - fila[0] > 60:
            fila.popleft()
        if len(fila) >= cfg.limite_analises_por_minuto:
            raise ErroLimiteRequisicoes()
        fila.append(agora)


limitar_analises = LimitadorTaxa()
