"""Regras explicáveis: urgência, órgão, prazo e quando chamar um humano.

A categoria vem do modelo de NLP. A urgência vem destas regras, porque ela
precisa ser auditável: o gestor vê exatamente POR QUE um relato ficou
"crítico" (coluna "Por que essa urgência" da planilha de despacho).

Como funciona: cada regra procura um SINAL no texto (sem acentos, minúsculo)
e propõe um nível. Vale o MAIOR nível encontrado. "Baixa" só vale se nenhum
sinal de risco aparecer. As ideias são as mesmas do app Zelo: risco à vida
nunca fica abaixo de crítica, público vulnerável e risco à saúde sobem a
urgência e chuva forte prevista agrava alagamentos e árvores.

Histórico: a v1 foi medida em `dados/teste/casos_desenvolvimento.csv`; os erros
de lá motivaram a v2 (esta). A métrica final é medida num conjunto NOVO,
`dados/teste/casos_teste_rotulados.csv`, que não foi usado para ajustar nada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .classificador import preprocessar
from .referencia import PRAZO_DIAS, URGENCIAS, orgao_para

VERSAO_REGRAS = "v2"

_SEMAFORO = r"(?:semaforo|farol)"
_FALHA = r"(?:apagad|desligad|quebrad|nao funciona|piscando|sem funcionar)"
_FALHA_SEMAFORO = _SEMAFORO + r"\w*.{0,30}" + _FALHA

# (nível, motivo, padrão, categorias onde vale | None = todas)
REGRAS: list[tuple[str, str, re.Pattern, set[str] | None]] = [
    # --- CRÍTICA: risco imediato à vida ---------------------------------------
    ("critica", "risco de choque elétrico (fio ou cabo exposto)",
     re.compile(r"(?:fio|cabo|fiacao)\w*.{0,30}(?:solt|caid|caiu|desencapad|arrebent|no chao|pendurad|faisca)"
                r"|faisca|choque|curto[- ]circuito|eletrocut|luminaria.{0,25}(?:pendurad|caindo|solta)"), None),
    ("critica", "árvore ou estrutura com risco de queda",
     re.compile(r"arvore.{0,40}(?:caiu|caindo|tomb|ameaca|inclinad|rachad|apoiada na fiacao)"
                r"|(?:vai|pode|prestes a|ameacando|qualquer momento) cai|desab"), None),
    ("critica", "pessoas em risco em alagamento",
     re.compile(r"ilhad|arrastad|correnteza|agua (?:na|ate a) cintura"), None),
    ("critica", "buraco ou bueiro onde alguém pode cair",
     re.compile(r"cratera|bueiro (?:aberto|sem tampa)|sem tampa|cabe um carro|alguem pode cair dentro"), None),
    ("critica", "semáforo sem funcionar em cruzamento ou perto de escola",
     re.compile(_FALHA_SEMAFORO + r".{0,60}(?:cruzamento|avenida|escola|colegio)"
                r"|(?:cruzamento|avenida).{0,40}" + _FALHA), {"sinalizacao_transito"}),
    # --- ALTA ---------------------------------------------------------------------
    ("alta", "envolve público vulnerável",
     re.compile(r"cadeirante|cadeira de rodas|idos[oa]|\bavo\b|deficien|cego|muleta|andador|carrinho de bebe"
                r"|crianca|escola|colegio|creche|ubs|hospital|gestante"), None),
    ("alta", "já houve queda ou acidente",
     re.compile(r"(?:quase|ja) ca(?:i|iu)|(?:moto|gente|pessoa|alguem|crianca|senhora|idos[oa])\w* (?:\w+ )?ca(?:i|em|iu)\b"
                r"|acidente|batida|machuc|ferid|tropec|derrap"), None),
    ("alta", "pedestre forçado a andar na rua",
     re.compile(r"\b(?:anda\w*|ir|vai|vou|passa\w*) (?:pela|na|no meio da) rua|meio dos carros|piso tatil"), None),
    ("alta", "risco à saúde (pragas, água parada, esgoto)",
     re.compile(r"\brato|barata|dengue|mosquito|esgoto|agua suja"), None),
    ("alta", "rua escura aumenta o risco para pedestres",
     re.compile(r"escur|breu|sem luz|assalto|ninguem tem coragem"), {"iluminacao_publica", "arvore_poda"}),
    ("alta", "sinalização de trânsito sem funcionar",
     re.compile(_FALHA_SEMAFORO + r"|placa de pare|(?:faixa|lombada).{0,30}(?:apagad|sumiu|sem pintura)"),
     {"sinalizacao_transito", "arvore_poda"}),
    ("alta", "visibilidade de motoristas comprometida",
     re.compile(r"(?:cobrindo|tampando|escondendo).{0,25}(?:semaforo|farol|placa)|nao enxerg"), None),
    ("alta", "água invadindo casas ou alagando a rua",
     re.compile(r"invad|entr\w* (?:nas|na|em) casa|transbord|alagou|virar rio"), {"alagamento_drenagem"}),
    ("alta", "galhos caindo ou pendurados",
     re.compile(r"galho.{0,30}(?:caem|caindo|pendurad|quebrad)|seca e morta|\bmorta\b"), {"arvore_poda"}),
    # --- BAIXA (só vale se nenhum sinal acima aparecer) ---------------------------------
    ("baixa", "relato indica baixo impacto",
     re.compile(r"pequen[oa]|nao (?:atrapalha|e urgente|tem pressa)|quando (?:puder|der)|sem pressa|"
                r"estetic|desbotad|feio|\btort[oa]\b|um pouco|fraquinh|desperdic|"
                r"mas (?:esta|ta) (?:escoando|funcionando)|(?:gostaria de|quero) solicitar poda|"
                r"segunda via|como faco|quero saber|informac|elogi|parabeniz"), None),
]

_ORDEM = {u: i for i, u in enumerate(URGENCIAS)}


def _subir(u: str) -> str:
    return URGENCIAS[min(_ORDEM[u] + 1, len(URGENCIAS) - 1)]


@dataclass
class Decisao:
    urgencia: str
    orgao: str
    prazo_dias: int
    justificativa: list[str] = field(default_factory=list)
    motivos_revisao: list[str] = field(default_factory=list)

    @property
    def precisa_revisao(self) -> bool:
        return bool(self.motivos_revisao)


def calcular_urgencia(descricao: str, categoria: str, chuva_mm: float | None,
                      limiar_chuva: float = 20.0) -> tuple[str, list[str]]:
    texto = preprocessar(descricao)
    achados = [(nivel, motivo) for nivel, motivo, padrao, cats in REGRAS
               if (cats is None or categoria in cats) and padrao.search(texto)]

    riscos = [(n, m) for n, m in achados if n != "baixa"]
    if riscos:
        urgencia = max((n for n, _ in riscos), key=_ORDEM.get)
        motivos = [m for n, m in riscos if n == urgencia]
    elif achados:
        urgencia, motivos = "baixa", [achados[0][1]]
    else:
        urgencia, motivos = "media", ["sem sinais de risco: urgência padrão"]

    if (chuva_mm is not None and chuva_mm >= limiar_chuva
            and categoria in ("alagamento_drenagem", "arvore_poda") and urgencia != "critica"):
        urgencia = _subir(urgencia)
        motivos.append(f"previsão de {chuva_mm:.0f} mm de chuva hoje no bairro (Open-Meteo)")

    return urgencia, motivos


def decidir(descricao: str, bairro: str, categoria: str, confianca: float,
            chuva_mm: float | None, limiar_confianca: float,
            limiar_chuva: float = 20.0, urgencia_informada: str | None = None) -> Decisao:
    if urgencia_informada:  # relato do app: urgência já confirmada pelo cidadão
        urgencia, justificativa = urgencia_informada, ["urgência confirmada no app Zelo"]
        regra, motivo_regra = calcular_urgencia(descricao, categoria, chuva_mm, limiar_chuva)
        if _ORDEM[regra] > _ORDEM[urgencia]:
            urgencia = regra
            justificativa.append(f"elevada pelo robô: {motivo_regra[-1]}")
    else:
        urgencia, justificativa = calcular_urgencia(descricao, categoria, chuva_mm, limiar_chuva)

    revisao: list[str] = []
    if confianca < limiar_confianca:
        revisao.append(f"baixa confiança da IA ({confianca:.0%})")
    if categoria == "outros":
        revisao.append("relato fora das categorias de zeladoria")

    return Decisao(
        urgencia=urgencia,
        orgao=orgao_para(categoria, bairro),
        prazo_dias=PRAZO_DIAS[urgencia],
        justificativa=justificativa,
        motivos_revisao=revisao,
    )
