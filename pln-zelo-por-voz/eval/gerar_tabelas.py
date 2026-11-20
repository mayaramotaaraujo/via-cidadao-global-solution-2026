"""Junta os resultados de todas as avaliações em results/resumo_metricas.md,
com tabelas prontas para colar no relatório.

Uso:  python -m eval.gerar_tabelas
"""
from __future__ import annotations

import csv

from eval.common import RESULTS


def read(name: str) -> list[dict]:
    p = RESULTS / name
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def table(rows: list[dict], cols: list[tuple[str, str]], fmt: dict | None = None) -> str:
    fmt = fmt or {}
    head = "| " + " | ".join(t for _, t in cols) + " |\n|" + "---|" * len(cols) + "\n"
    body = ""
    for r in rows:
        vals = []
        for k, _ in cols:
            v = r.get(k, "")
            vals.append(fmt[k](v) if k in fmt and v != "" else str(v))
        body += "| " + " | ".join(vals) + " |\n"
    return head + body


pct = lambda v: f"{float(v) * 100:.1f}%"  # noqa: E731
pct100 = lambda v: f"{float(v):.1f}%"  # noqa: E731
sec = lambda v: f"{float(v):.2f}"  # noqa: E731


def main() -> None:
    md = ["# Resumo das métricas do Zelo\n"]

    stt = read("stt_resumo.csv")
    if stt:
        md.append("## STT: comparação de modelos (20 áudios)\n")
        md.append(table(stt, [("modelo", "Modelo"), ("n_audios", "Áudios"), ("wer_corpus", "WER"),
                              ("latencia_media_s", "Latência média (s)"), ("latencia_p90_s", "Latência p90 (s)"), ("rtf_medio", "RTF")],
                        {"wer_corpus": pct, "latencia_media_s": sec, "latencia_p90_s": sec}))
        vies = read("stt_vies.csv")
        if vies:
            md.append("\n## STT: análise de viés (WER por grupo)\n")
            md.append(table(vies, [("modelo", "Modelo"), ("dimensao", "Dimensão"), ("grupo", "Grupo"), ("n", "Áudios"), ("wer", "WER")],
                            {"wer": pct}))

    llm = read("llm_resumo.csv")
    if llm:
        md.append("\n## LLM e diálogo (30 perguntas)\n")
        md.append(table(llm, [("modelo", "Modelo"), ("acerto_no_tema_pct", "Acerto no tema (25)"),
                              ("acerto_continuacao_pct", "Continuação (5)"), ("admite_nao_saber_pct", "Admite não saber (2)"),
                              ("recusas_adequadas_pct", "Recusas adequadas (5)"), ("acerto_geral_pct", "Geral (30)"),
                              ("latencia_llm_media_s", "Latência LLM (s)")],
                        {k: pct100 for k in ["acerto_no_tema_pct", "acerto_continuacao_pct", "admite_nao_saber_pct",
                                             "recusas_adequadas_pct", "acerto_geral_pct"]} | {"latencia_llm_media_s": sec}))

    tts = read("tts_resumo.csv")
    if tts:
        md.append("\n## TTS (10 amostras)\n")
        md.append(table(tts, [("avaliadores", "Avaliadores"), ("avaliacoes", "Avaliações"), ("naturalidade_media", "Naturalidade (1-5)"),
                              ("naturalidade_dp", "DP"), ("clareza_media", "Clareza (1-5)"), ("clareza_dp", "DP")]))
        amostras = read("tts_por_amostra.csv")
        if amostras:
            md.append("\n" + table(amostras, [("amostra", "Amostra"), ("naturalidade_media", "Naturalidade"), ("clareza_media", "Clareza")]))

    e2e = read("e2e_resumo.csv")
    if e2e:
        md.append("\n## Ponta a ponta (10 conversas, 30 turnos): latência em segundos\n")
        md.append(table(e2e, [("etapa", "Etapa"), ("media", "Média"), ("mediana", "Mediana"), ("p90", "p90"), ("max", "Máx")],
                        {k: sec for k in ["media", "mediana", "p90", "max"]}))

    out = RESULTS / "resumo_metricas.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
