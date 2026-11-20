"""Avaliação do STT: WER (jiwer), latência, comparação de modelos e análise de viés.

Uso:
    python -m eval.eval_stt                       # compara Whisper base x small
    python -m eval.eval_stt --models tiny base small
    python -m eval.eval_stt --compare-prompt      # também mede o efeito do prompt de domínio

Saídas em results/: stt_detalhado.csv, stt_resumo.csv, stt_vies.csv
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict

import jiwer

from eval.common import MATERIAL, RESULTS, describe, find_audio, normalize_for_wer
from zelo.stt import WhisperSTT


def corpus_wer(refs: list[str], hyps: list[str]) -> float:
    return jiwer.wer(refs, hyps) if refs else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["base", "small"])
    ap.add_argument("--roteiro", default=str(MATERIAL / "stt" / "roteiro_gravacao.csv"))
    ap.add_argument("--audio-dir", default=str(MATERIAL / "stt" / "audios"))
    ap.add_argument("--compare-prompt", action="store_true", help="roda cada modelo com e sem prompt de domínio")
    args = ap.parse_args()

    from pathlib import Path

    audio_dir = Path(args.audio_dir)
    rows = list(csv.DictReader(open(args.roteiro, encoding="utf-8")))
    found = [(r, find_audio(audio_dir, r["arquivo"])) for r in rows]
    missing = [r["arquivo"] for r, p in found if p is None]
    if missing:
        print(f"ATENÇÃO: {len(missing)} áudio(s) não encontrados em {audio_dir}: {', '.join(missing)}")
    found = [(r, p) for r, p in found if p is not None]
    if not found:
        raise SystemExit("Nenhum áudio encontrado. Grave os arquivos do roteiro primeiro (veja material_teste/stt/LEIA-ME.md).")

    configs = [(m, True) for m in args.models]
    if args.compare_prompt:
        configs += [(m, False) for m in args.models]

    detalhado, resumo, vies = [], [], []
    for model, use_prompt in configs:
        label = f"{model}{'' if use_prompt else '-sem-prompt'}"
        stt = WhisperSTT(model_size=model, use_domain_prompt=use_prompt)
        print(f"\n== {label}: carregando modelo...")
        stt.warmup()
        refs, hyps, lats, rtfs = [], [], [], []
        groups: dict[tuple[str, str], tuple[list, list]] = defaultdict(lambda: ([], []))
        for r, path in found:
            res = stt.transcribe(str(path))
            ref_n, hyp_n = normalize_for_wer(r["referencia"]), normalize_for_wer(res.text)
            w = jiwer.wer(ref_n, hyp_n) if ref_n else 0.0
            refs.append(ref_n)
            hyps.append(hyp_n)
            lats.append(res.elapsed_s)
            rtf = res.elapsed_s / res.duration_audio_s if res.duration_audio_s else 0
            rtfs.append(rtf)
            for g in ("falante", "genero", "faixa_etaria", "ruido"):
                groups[(g, r[g])][0].append(ref_n)
                groups[(g, r[g])][1].append(hyp_n)
            detalhado.append({
                "modelo": label, "arquivo": path.name, "falante": r["falante"], "genero": r["genero"],
                "faixa_etaria": r["faixa_etaria"], "ruido": r["ruido"], "referencia": r["referencia"],
                "transcricao": res.text, "wer": round(w, 4), "latencia_s": round(res.elapsed_s, 3),
                "duracao_audio_s": round(res.duration_audio_s, 2), "rtf": round(rtf, 3),
            })
            print(f"  {path.name}: WER={w:.2%}  {res.elapsed_s:.2f}s  | {res.text}")

        lat = describe(lats)
        resumo.append({
            "modelo": label, "n_audios": len(refs), "wer_corpus": round(corpus_wer(refs, hyps), 4),
            "wer_medio_por_audio": round(sum(d["wer"] for d in detalhado if d["modelo"] == label) / len(refs), 4),
            "latencia_media_s": lat["media"], "latencia_p90_s": lat["p90"],
            "rtf_medio": round(sum(rtfs) / len(rtfs), 3),
        })
        for (g, val), (rr, hh) in sorted(groups.items()):
            vies.append({"modelo": label, "dimensao": g, "grupo": val, "n": len(rr), "wer": round(corpus_wer(rr, hh), 4)})

    def save(name, data):
        with open(RESULTS / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)

    save("stt_detalhado.csv", detalhado)
    save("stt_resumo.csv", resumo)
    save("stt_vies.csv", vies)

    print("\n=== RESUMO STT ===")
    for r in resumo:
        print(f"{r['modelo']:>18}: WER {r['wer_corpus']:.2%} | latência média {r['latencia_media_s']:.2f}s | RTF {r['rtf_medio']:.2f}")
    print("\n=== VIÉS (WER por grupo) ===")
    for v in vies:
        print(f"{v['modelo']:>18} | {v['dimensao']:<13} {v['grupo']:<12} n={v['n']:<3} WER {v['wer']:.2%}")
    print(f"\nArquivos salvos em {RESULTS}")


if __name__ == "__main__":
    main()
