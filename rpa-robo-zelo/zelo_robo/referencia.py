"""Tabelas de referência do protótipo (mesmas categorias do app Zelo).

As coordenadas são o centro aproximado de cada distrito e servem só para
consultar a previsão de chuva. O robô nunca usa endereço exato do cidadão.
"""

from __future__ import annotations

import unicodedata

CATEGORIAS = [
    "buraco_pavimentacao",
    "iluminacao_publica",
    "calcada_acessibilidade",
    "alagamento_drenagem",
    "lixo_entulho",
    "arvore_poda",
    "sinalizacao_transito",
    "outros",
]

URGENCIAS = ["baixa", "media", "alta", "critica"]

# distrito: (subprefeitura, zona, latitude, longitude)
BAIRROS: dict[str, tuple[str, str, float, float]] = {
    "Sé": ("Sé", "Centro", -23.5505, -46.6333),
    "República": ("Sé", "Centro", -23.5440, -46.6420),
    "Bela Vista": ("Sé", "Centro", -23.5614, -46.6469),
    "Consolação": ("Sé", "Centro", -23.5530, -46.6600),
    "Liberdade": ("Sé", "Centro", -23.5587, -46.6350),
    "Brás": ("Mooca", "Centro", -23.5440, -46.6160),
    "Mooca": ("Mooca", "Leste", -23.5600, -46.5990),
    "Tatuapé": ("Mooca", "Leste", -23.5400, -46.5760),
    "Vila Prudente": ("Vila Prudente", "Leste", -23.5830, -46.5820),
    "Sapopemba": ("Sapopemba", "Leste", -23.6020, -46.5110),
    "Penha": ("Penha", "Leste", -23.5250, -46.5430),
    "Itaquera": ("Itaquera", "Leste", -23.5370, -46.4570),
    "São Miguel Paulista": ("São Miguel", "Leste", -23.4980, -46.4440),
    "Guaianases": ("Guaianases", "Leste", -23.5420, -46.4140),
    "Cidade Tiradentes": ("Cidade Tiradentes", "Leste", -23.5820, -46.4090),
    "Santana": ("Santana/Tucuruvi", "Norte", -23.5020, -46.6250),
    "Tucuruvi": ("Santana/Tucuruvi", "Norte", -23.4800, -46.6030),
    "Vila Maria": ("Vila Maria/Vila Guilherme", "Norte", -23.5150, -46.5820),
    "Freguesia do Ó": ("Freguesia/Brasilândia", "Norte", -23.4950, -46.6950),
    "Brasilândia": ("Freguesia/Brasilândia", "Norte", -23.4680, -46.6880),
    "Pirituba": ("Pirituba/Jaraguá", "Norte", -23.4860, -46.7260),
    "Perus": ("Perus/Anhanguera", "Norte", -23.4040, -46.7540),
    "Lapa": ("Lapa", "Oeste", -23.5270, -46.7030),
    "Pinheiros": ("Pinheiros", "Oeste", -23.5670, -46.6930),
    "Butantã": ("Butantã", "Oeste", -23.5720, -46.7080),
    "Vila Mariana": ("Vila Mariana", "Sul", -23.5890, -46.6340),
    "Ipiranga": ("Ipiranga", "Sul", -23.5890, -46.6100),
    "Jabaquara": ("Jabaquara", "Sul", -23.6450, -46.6410),
    "Santo Amaro": ("Santo Amaro", "Sul", -23.6540, -46.7100),
    "Campo Limpo": ("Campo Limpo", "Sul", -23.6330, -46.7590),
    "Capão Redondo": ("Campo Limpo", "Sul", -23.6710, -46.7790),
    "Jardim Ângela": ("M'Boi Mirim", "Sul", -23.7120, -46.7700),
    "Grajaú": ("Capela do Socorro", "Sul", -23.7690, -46.6970),
    "Parelheiros": ("Parelheiros", "Sul", -23.8300, -46.7280),
}

# Órgãos que NÃO dependem da subprefeitura (os demais vão para a subprefeitura do bairro).
ORGAOS_FIXOS = {
    "iluminacao_publica": "ILUME (Iluminação Pública)",
    "lixo_entulho": "SP Regula (Limpeza Urbana)",
    "sinalizacao_transito": "CET (Engenharia de Tráfego)",
    "outros": "SP156 (Triagem Manual)",
}

# E-mails FICTÍCIOS (domínio example.com é reservado para testes, RFC 2606).
EMAIL_ORGAOS_FIXOS = {
    "ILUME (Iluminação Pública)": "ilume.despacho@example.com",
    "SP Regula (Limpeza Urbana)": "spregula.despacho@example.com",
    "CET (Engenharia de Tráfego)": "cet.despacho@example.com",
    "SP156 (Triagem Manual)": "sp156.triagem@example.com",
}

# Prazos de REFERÊNCIA do protótipo (não são prazos oficiais da Prefeitura).
PRAZO_DIAS = {"critica": 1, "alta": 3, "media": 10, "baixa": 30}


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


_INDICE_BAIRROS = {_sem_acento(n).lower(): n for n in BAIRROS}


def normalizar_bairro(valor: str | None) -> str | None:
    """'sao miguel paulista ' -> 'São Miguel Paulista'. None se não for um bairro conhecido."""
    if not valor:
        return None
    chave = " ".join(_sem_acento(str(valor)).lower().split())
    return _INDICE_BAIRROS.get(chave)


def orgao_para(categoria: str, bairro: str) -> str:
    if categoria in ORGAOS_FIXOS:
        return ORGAOS_FIXOS[categoria]
    return f"Subprefeitura {BAIRROS[bairro][0]}"


def email_do_orgao(orgao: str) -> str:
    if orgao in EMAIL_ORGAOS_FIXOS:
        return EMAIL_ORGAOS_FIXOS[orgao]
    slug = _sem_acento(orgao.replace("Subprefeitura ", "")).lower()
    slug = "".join(c if c.isalnum() else "." for c in slug).strip(".")
    while ".." in slug:
        slug = slug.replace("..", ".")
    return f"zeladoria.{slug}@example.com"


def coordenadas(bairro: str) -> tuple[float, float]:
    _, _, lat, lon = BAIRROS[bairro]
    return lat, lon
