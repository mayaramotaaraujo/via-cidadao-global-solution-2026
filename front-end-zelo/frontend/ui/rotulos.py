"""Rótulos em linguagem simples e cores semânticas (fonte única da verdade)."""

CATEGORIAS = {
    "buraco_pavimentacao": "Buraco ou asfalto",
    "iluminacao_publica": "Iluminação pública",
    "calcada_acessibilidade": "Calçada e acessibilidade",
    "alagamento_drenagem": "Alagamento ou bueiro",
    "lixo_entulho": "Lixo e entulho",
    "arvore_poda": "Árvore e poda",
    "sinalizacao_transito": "Sinalização e semáforo",
    "outros": "Outros",
}

# Cores com contraste ≥ 4.5:1 sob texto branco (WCAG AA).
# Cada nível também tem uma FORMA de placa de trânsito e o NOME escrito:
# a informação nunca depende só da cor.
URGENCIAS = {
    "critica": {"rotulo": "Crítica", "cor": "#B3261E", "forma": "octogono", "descricao": "Risco imediato"},
    "alta": {"rotulo": "Alta", "cor": "#B54708", "forma": "triangulo", "descricao": "Resolver em poucos dias"},
    "media": {"rotulo": "Média", "cor": "#8A5A00", "forma": "losango", "descricao": "Atrapalha a rotina"},
    "baixa": {"rotulo": "Baixa", "cor": "#1E7B34", "forma": "quadrado", "descricao": "Pequeno incômodo"},
}
ORDEM_URGENCIA = ["critica", "alta", "media", "baixa"]

STATUS = {
    "recebido": "Recebido",
    "em_analise": "Em análise",
    "encaminhado": "Encaminhado à equipe",
    "resolvido": "Resolvido",
    "rejeitado": "Não procede",
}


def rotulo_categoria(chave: str) -> str:
    return CATEGORIAS.get(chave, chave)


def rotulo_urgencia(chave: str) -> str:
    u = URGENCIAS.get(chave)
    return u["rotulo"] if u else chave


def rotulo_status(chave: str) -> str:
    return STATUS.get(chave, chave)


MAPA_CORES_URGENCIA = {URGENCIAS[k]["rotulo"]: URGENCIAS[k]["cor"] for k in ORDEM_URGENCIA}
