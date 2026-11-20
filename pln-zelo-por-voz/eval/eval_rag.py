"""Avaliação da recuperação (RAG), 100% offline.

Para cada pergunta do tema, verifica se o documento correto da base aparece
entre os trechos recuperados (recall@k) e em que posição (MRR). Perguntas de
continuação usam a pergunta anterior da mesma conversa, como no app.

Uso:  python -m eval.eval_rag
"""
from __future__ import annotations

import csv
from collections import OrderedDict

from eval.common import MATERIAL, RESULTS
from zelo.config import settings
from zelo.pipeline import Conversation, VoicePipeline


def main() -> None:
    pipe = VoicePipeline(llm=None, log_latency=False)
    qs = [q for q in csv.DictReader(open(MATERIAL / "llm" / "perguntas_avaliacao.csv", encoding="utf-8")) if q["doc_esperado"]]
    convs: "OrderedDict[str, list[dict]]" = OrderedDict()
    for q in qs:
        convs.setdefault(q["conversa"], []).append(q)

    rows = []
    for _, items in convs.items():
        conv = Conversation()
        for q in items:
            chunks = pipe.retrieve(q["pergunta"], conv)
            docs = [c.doc for c in chunks]
            rank = docs.index(q["doc_esperado"]) + 1 if q["doc_esperado"] in docs else 0
            rows.append({"id": q["id"], "tipo": q["tipo"], "pergunta": q["pergunta"], "doc_esperado": q["doc_esperado"],
                         "top1": f"{chunks[0].doc} > {chunks[0].title}" if chunks else "", "posicao": rank})
            conv.add(q["pergunta"], "(resposta)")

    k = settings.rag_top_k
    n = len(rows)
    recall = sum(r["posicao"] > 0 for r in rows) / n
    top1 = sum(r["posicao"] == 1 for r in rows) / n
    mrr = sum(1 / r["posicao"] for r in rows if r["posicao"]) / n
    with open(RESULTS / "rag_detalhado.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(RESULTS / "rag_resumo.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["n_perguntas", "k", "acerto_top1", f"recall_at_{k}", "mrr"])
        w.writerow([n, k, round(top1, 4), round(recall, 4), round(mrr, 4)])
    for r in rows:
        print(f"[{r['id']:>2}] pos={r['posicao']} | {r['pergunta'][:55]:<55} -> {r['top1']}")
    print(f"\n{n} perguntas | top-1 {top1:.1%} | recall@{k} {recall:.1%} | MRR {mrr:.3f}")


if __name__ == "__main__":
    main()
