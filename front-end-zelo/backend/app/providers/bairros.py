"""Bairros/distritos de São Paulo atendidos pelo protótipo.

Coordenadas APROXIMADAS do centro de cada distrito. São usadas para:
1. consultar a previsão de chuva (Open-Meteo) da região do relato;
2. posicionar o relato no mapa do painel.

Por privacidade, o sistema não pede endereço exato nem GPS do cidadão:
o ponto do mapa é o centro do bairro com um pequeno deslocamento
determinístico (para os pontos não ficarem empilhados).
"""

import hashlib

# nome: (zona, latitude, longitude)
BAIRROS: dict[str, tuple[str, float, float]] = {
    "Sé": ("Centro", -23.5505, -46.6333),
    "República": ("Centro", -23.5440, -46.6420),
    "Bela Vista": ("Centro", -23.5614, -46.6469),
    "Consolação": ("Centro", -23.5530, -46.6600),
    "Liberdade": ("Centro", -23.5587, -46.6350),
    "Brás": ("Centro", -23.5440, -46.6160),
    "Mooca": ("Leste", -23.5600, -46.5990),
    "Tatuapé": ("Leste", -23.5400, -46.5760),
    "Vila Prudente": ("Leste", -23.5830, -46.5820),
    "Sapopemba": ("Leste", -23.6020, -46.5110),
    "Penha": ("Leste", -23.5250, -46.5430),
    "Itaquera": ("Leste", -23.5370, -46.4570),
    "São Miguel Paulista": ("Leste", -23.4980, -46.4440),
    "Guaianases": ("Leste", -23.5420, -46.4140),
    "Cidade Tiradentes": ("Leste", -23.5820, -46.4090),
    "Santana": ("Norte", -23.5020, -46.6250),
    "Tucuruvi": ("Norte", -23.4800, -46.6030),
    "Vila Maria": ("Norte", -23.5150, -46.5820),
    "Freguesia do Ó": ("Norte", -23.4950, -46.6950),
    "Brasilândia": ("Norte", -23.4680, -46.6880),
    "Pirituba": ("Norte", -23.4860, -46.7260),
    "Perus": ("Norte", -23.4040, -46.7540),
    "Lapa": ("Oeste", -23.5270, -46.7030),
    "Pinheiros": ("Oeste", -23.5670, -46.6930),
    "Butantã": ("Oeste", -23.5720, -46.7080),
    "Vila Mariana": ("Sul", -23.5890, -46.6340),
    "Ipiranga": ("Sul", -23.5890, -46.6100),
    "Jabaquara": ("Sul", -23.6450, -46.6410),
    "Santo Amaro": ("Sul", -23.6540, -46.7100),
    "Campo Limpo": ("Sul", -23.6330, -46.7590),
    "Capão Redondo": ("Sul", -23.6710, -46.7790),
    "Jardim Ângela": ("Sul", -23.7120, -46.7700),
    "Grajaú": ("Sul", -23.7690, -46.6970),
    "Parelheiros": ("Sul", -23.8300, -46.7280),
}


def listar_bairros() -> list[dict]:
    return [{"nome": n, "zona": z} for n, (z, _, _) in sorted(BAIRROS.items())]


def coordenadas(bairro: str) -> tuple[float, float] | None:
    dados = BAIRROS.get(bairro)
    return (dados[1], dados[2]) if dados else None


def coordenadas_mapa(bairro: str, semente: str) -> tuple[float, float]:
    """Centro do bairro + deslocamento determinístico de até ~600 m."""
    base = coordenadas(bairro) or (-23.5505, -46.6333)
    h = hashlib.sha256(semente.encode()).digest()
    dlat = (h[0] / 255 - 0.5) * 0.011
    dlon = (h[1] / 255 - 0.5) * 0.011
    return round(base[0] + dlat, 5), round(base[1] + dlon, 5)
