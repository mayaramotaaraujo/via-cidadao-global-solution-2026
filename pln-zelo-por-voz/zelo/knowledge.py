"""Base de conhecimento (RAG leve).

Os documentos em kb/*.md foram escritos a partir de páginas oficiais da
Prefeitura de São Paulo, SP Regula e Defesa Civil (fonte indicada no topo de
cada arquivo). Cada seção "##" vira um trecho (chunk).

A busca é híbrida: TF-IDF de palavras (uni e bigramas) + TF-IDF de
n-gramas de caracteres (char_wb 3-5), com expansão de sinônimos do domínio
("luz" -> iluminação, "carro largado" -> veículo abandonado).
Escolhemos isso em vez de embeddings neurais porque:
  * roda 100% local e instantâneo (< 5 ms), sem custo e sem baixar modelo;
  * n-gramas de caracteres toleram erros de transcrição do STT
    ("bueiro"/"boeiro", "ecoponto"/"eco ponto");
  * a base é pequena e de vocabulário bem específico.
"""
from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import settings


# Sinônimos do jeito que o cidadão fala -> termos da base oficial.
SYNONYMS = {
    r"\bluz\b|l[aâ]mpada|poste|apagad|escur": "iluminação pública poste",
    r"buraco|asfalto|cratera": "tapa-buraco asfalto",
    r"carro|ve[ií]culo|carca[çc]a|moto\b": "veículo abandonado",
    r"[aá]rvore|galho|poda|tronco": "árvore poda",
    r"entulho|reforma|tijolo|cimento|ca[çc]amba": "entulho Ecoponto",
    r"sof[aá]|m[oó]ve(l|is)|colch[aã]o|geladeira|fog[aã]o": "Cata-Bagulho Ecoponto objetos grandes",
    r"bueiro|boeiro|boca de lobo|entupid": "bueiro boca de lobo",
    r"chuva|alag|enchente|inunda": "alagamento chuva Defesa Civil",
    r"rachadura|trinca|deslizamento|desliza|terra cedendo|cedendo": "risco de deslizamento rachaduras Defesa Civil",
    r"whats|zap": "WhatsApp Chat SP156",
    r"sabesp|comg[aá]s|concession[aá]ria|enel": "concessionária Sabesp Comgás Enel",
    r"sem luz|sem energia|falta de (luz|energia)|dentro de casa|minha casa": "energia dentro de casa Enel o que a Prefeitura não cuida",
    r"fa[ií]sca|fio": "fio partido faíscas Enel urgência",
    r"156|prefeitura|protocolo": "SP156 canais",
    r"prazo|demora|quantos dias|acompanhar|andamento": "protocolo e prazos de resposta",
    r"vem ver|algu[eé]m vem|vistori|depois que eu pedir|depois do pedido|o que acontece depois": "o que acontece depois do pedido vistoria técnico",
}


def expand_query(query: str) -> str:
    extra = [v for pat, v in SYNONYMS.items() if re.search(pat, query, re.IGNORECASE)]
    return query + (" " + " ".join(extra) if extra else "")


@dataclass
class Chunk:
    doc: str
    title: str
    text: str
    source: str

    def as_context(self) -> str:
        return f"[{self.doc} | {self.title}]\n{self.text}"


@dataclass
class RetrievalResult:
    chunks: list[Chunk]
    scores: list[float]
    elapsed_s: float

    @property
    def best_score(self) -> float:
        return max(self.scores) if self.scores else 0.0


STOPWORDS_PT = (
    "a o e é de da do das dos em no na nos nas um uma uns umas para pra pro por com sem que se me eu meu minha "
    "você voce ele ela isso esse essa este esta ao aos à às como qual quais quando onde quem tem ter ser está esta "
    "ou mas mais muito também tambem já ja não nao sim faz fazer posso pode dá da lá la aqui ai aí"
).split()
# Mesmo pré-processamento do vetorizador (sem acentos), para não gerar aviso de inconsistência.
STOPWORDS_PT = sorted({unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode() for w in STOPWORDS_PT})


def load_chunks(kb_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(kb_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        doc_title = re.search(r"^# (.+)$", raw, re.M)
        doc = doc_title.group(1).strip() if doc_title else path.stem
        src = re.search(r"^fonte:\s*(.+)$", raw, re.M)
        source = src.group(1).strip() if src else ""
        for part in re.split(r"^## ", raw, flags=re.M)[1:]:
            title, _, body = part.partition("\n")
            body = body.strip()
            if body:
                chunks.append(Chunk(doc=doc, title=title.strip(), text=body, source=source))
    return chunks


class KnowledgeBase:
    def __init__(self, kb_dir: Path | None = None) -> None:
        self.chunks = load_chunks(kb_dir or settings.kb_dir)
        if not self.chunks:
            raise RuntimeError("Base de conhecimento vazia: verifique a pasta kb/")
        self.char_vec = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), lowercase=True, strip_accents="unicode", sublinear_tf=True
        )
        self.word_vec = TfidfVectorizer(
            analyzer="word", ngram_range=(1, 2), lowercase=True, strip_accents="unicode",
            sublinear_tf=True, stop_words=STOPWORDS_PT,
        )
        corpus = [f"{c.doc} {c.title} {c.title} {c.text}" for c in self.chunks]
        self.char_m = self.char_vec.fit_transform(corpus)
        self.word_m = self.word_vec.fit_transform(corpus)

    def search(self, query: str, top_k: int | None = None, min_score: float | None = None) -> RetrievalResult:
        top_k = top_k or settings.rag_top_k
        min_score = settings.rag_min_score if min_score is None else min_score
        t0 = time.perf_counter()
        q = expand_query(query)
        sims = 0.5 * cosine_similarity(self.char_vec.transform([q]), self.char_m)[0] + 0.5 * cosine_similarity(
            self.word_vec.transform([q]), self.word_m
        )[0]
        order = sims.argsort()[::-1][:top_k]
        picked = [(self.chunks[i], float(sims[i])) for i in order if sims[i] >= min_score]
        return RetrievalResult(
            chunks=[c for c, _ in picked],
            scores=[s for _, s in picked],
            elapsed_s=time.perf_counter() - t0,
        )
