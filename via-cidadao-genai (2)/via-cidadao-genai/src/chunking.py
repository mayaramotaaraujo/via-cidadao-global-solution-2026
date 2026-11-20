"""Leitura dos documentos e divisão em trechos (chunks).

Estratégia principal (híbrida): primeiro divide pela estrutura do documento
(cada seção que começa com "## " vira um bloco). Se o bloco for maior que o
tamanho máximo, divide por frases, com overlap de frases entre trechos.

Também existe a estratégia "fixa" (por quantidade de caracteres), usada só
para comparar nos experimentos.
"""
import re
from pathlib import Path


def ler_documento(caminho):
    """Lê um .md com cabeçalho simples (entre ---) e devolve (metadados, texto)."""
    bruto = Path(caminho).read_text(encoding="utf-8")
    meta = {}
    corpo = bruto
    if bruto.startswith("---"):
        _, cab, corpo = bruto.split("---", 2)
        for linha in cab.strip().splitlines():
            if ":" in linha:
                k, v = linha.split(":", 1)
                meta[k.strip()] = v.strip()
    meta["arquivo"] = Path(caminho).name
    return meta, corpo.strip()


def separar_frases(texto):
    partes = re.split(r"(?<=[.!?])\s+", texto.strip())
    return [p.strip() for p in partes if p.strip()]


def _secoes(corpo):
    """Devolve lista de (titulo_da_secao, texto)."""
    achados = re.split(r"^## ", corpo, flags=re.M)
    secoes = []
    for bloco in achados:
        bloco = bloco.strip()
        if not bloco:
            continue
        linhas = bloco.split("\n", 1)
        titulo = linhas[0].strip()
        texto = linhas[1].strip() if len(linhas) > 1 else ""
        if texto:
            secoes.append((titulo, texto))
    return secoes


def chunk_estrutural(meta, corpo, max_chars=700, overlap_frases=1):
    chunks = []
    for titulo, texto in _secoes(corpo):
        if len(texto) <= max_chars:
            grupos = [texto]
        else:
            frases = separar_frases(texto)
            grupos, atual = [], []
            for f in frases:
                if atual and len(" ".join(atual + [f])) > max_chars:
                    grupos.append(" ".join(atual))
                    atual = atual[-overlap_frases:] if overlap_frases else []
                atual.append(f)
            if atual:
                grupos.append(" ".join(atual))
        for i, g in enumerate(grupos):
            chunks.append({
                "id": f"{meta['id']}#{len(chunks)}",
                "doc_id": meta["id"],
                "secao": titulo,
                "titulo_doc": meta.get("titulo", ""),
                "url": meta.get("url", ""),
                "consulta": meta.get("consulta", ""),
                # título do documento e da seção entram no texto indexado (cabeçalho de contexto),
                # porque uma seção como "Prazo" sozinha não diz de qual serviço está falando
                "texto": f"{meta.get('titulo', '')}. {titulo}. {g}",
                "corpo": g,
            })
    return chunks


def chunk_fixo(meta, corpo, tamanho=300, overlap=0):
    """Divisão simples por caracteres, ignorando a estrutura. Só para comparação."""
    limpo = re.sub(r"^## ", "", corpo, flags=re.M)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    passo = max(1, tamanho - overlap)
    chunks = []
    for ini in range(0, len(limpo), passo):
        pedaco = limpo[ini:ini + tamanho]
        if len(pedaco) < 40:
            continue
        chunks.append({
            "id": f"{meta['id']}#{len(chunks)}",
            "doc_id": meta["id"],
            "secao": "",
            "titulo_doc": meta.get("titulo", ""),
            "url": meta.get("url", ""),
            "consulta": meta.get("consulta", ""),
            "texto": pedaco,
            "corpo": pedaco,
        })
    return chunks


CONFIGS = {
    "A_fixo_300_sem_overlap": dict(modo="fixo", tamanho=300, overlap=0),
    "B_fixo_600_overlap_100": dict(modo="fixo", tamanho=600, overlap=100),
    "C_estrutural_700_overlap_1frase": dict(modo="estrutural", max_chars=700, overlap_frases=1),
}


def carregar_corpus(pasta, config):
    chunks = []
    for caminho in sorted(Path(pasta).glob("*.md")):
        meta, corpo = ler_documento(caminho)
        if config["modo"] == "fixo":
            chunks += chunk_fixo(meta, corpo, config["tamanho"], config["overlap"])
        else:
            chunks += chunk_estrutural(meta, corpo, config["max_chars"], config["overlap_frases"])
    return chunks
