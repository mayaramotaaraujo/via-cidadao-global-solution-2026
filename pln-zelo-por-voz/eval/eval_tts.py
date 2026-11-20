"""Avaliação do TTS.

Etapa 1 (gerar):   python -m eval.eval_tts gerar
    Adapta as 10 frases para fala, sintetiza os áudios em material_teste/tts/audios/
    e cria a planilha material_teste/tts/avaliacao_tts.csv para 3+ avaliadores.

Etapa 2 (resumir): python -m eval.eval_tts resumir
    Depois que os avaliadores preencherem as notas (1 a 5), calcula média e
    desvio de naturalidade e clareza por amostra, por avaliador e no geral.
"""
from __future__ import annotations

import argparse
import csv
import statistics as st

from eval.common import MATERIAL, RESULTS, describe
from zelo.speech_adapter import adapt_for_speech
from zelo.tts import EdgeTTS

TTS_DIR = MATERIAL / "tts"
SHEET = TTS_DIR / "avaliacao_tts.csv"


def gerar(avaliadores: list[str]) -> None:
    tts = EdgeTTS()
    frases = list(csv.DictReader(open(TTS_DIR / "frases_tts.csv", encoding="utf-8")))
    lat, amostras = [], []
    for f in frases:
        adaptado = adapt_for_speech(f["texto_original"])
        path = TTS_DIR / "audios" / f"tts_{int(f['amostra']):02d}.mp3"
        res = tts.synthesize(adaptado, path)
        lat.append(res.elapsed_s)
        amostras.append({"amostra": f["amostra"], "arquivo": path.name, "texto_original": f["texto_original"],
                         "texto_adaptado": adaptado, "latencia_tts_s": round(res.elapsed_s, 3)})
        print(f"[{f['amostra']}] {res.elapsed_s:.2f}s  {adaptado}")

    with open(TTS_DIR / "amostras_tts.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(amostras[0].keys()))
        w.writeheader()
        w.writerows(amostras)

    if not SHEET.exists():
        with open(SHEET, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["avaliador", "amostra", "arquivo", "naturalidade_1a5", "clareza_1a5", "comentario"])
            for a in avaliadores:
                for s in amostras:
                    w.writerow([a, s["amostra"], s["arquivo"], "", "", ""])
        print(f"\nPlanilha criada: {SHEET}")
    print(f"Voz: {tts.name} | latência TTS média {describe(lat)['media']:.2f}s")


def resumir() -> None:
    rows = [r for r in csv.DictReader(open(SHEET, encoding="utf-8")) if r["naturalidade_1a5"] and r["clareza_1a5"]]
    if not rows:
        raise SystemExit("A planilha ainda não tem notas preenchidas.")
    nat = [float(r["naturalidade_1a5"]) for r in rows]
    cla = [float(r["clareza_1a5"]) for r in rows]
    sd = lambda v: round(st.stdev(v), 2) if len(v) > 1 else 0.0  # noqa: E731

    por_amostra = []
    for a in sorted({r["amostra"] for r in rows}, key=int):
        sub = [r for r in rows if r["amostra"] == a]
        n = [float(r["naturalidade_1a5"]) for r in sub]
        c = [float(r["clareza_1a5"]) for r in sub]
        por_amostra.append({"amostra": a, "avaliacoes": len(sub), "naturalidade_media": round(st.mean(n), 2),
                            "clareza_media": round(st.mean(c), 2)})
    por_avaliador = []
    for a in sorted({r["avaliador"] for r in rows}):
        sub = [r for r in rows if r["avaliador"] == a]
        por_avaliador.append({"avaliador": a, "naturalidade_media": round(st.mean(float(r["naturalidade_1a5"]) for r in sub), 2),
                              "clareza_media": round(st.mean(float(r["clareza_1a5"]) for r in sub), 2)})
    geral = {"avaliadores": len({r["avaliador"] for r in rows}), "avaliacoes": len(rows),
             "naturalidade_media": round(st.mean(nat), 2), "naturalidade_dp": sd(nat),
             "clareza_media": round(st.mean(cla), 2), "clareza_dp": sd(cla)}

    for name, data in [("tts_por_amostra.csv", por_amostra), ("tts_por_avaliador.csv", por_avaliador), ("tts_resumo.csv", [geral])]:
        with open(RESULTS / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)
    print(geral)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("etapa", choices=["gerar", "resumir"])
    ap.add_argument("--avaliadores", nargs="+", default=["A1", "A2", "A3"])
    args = ap.parse_args()
    gerar(args.avaliadores) if args.etapa == "gerar" else resumir()


if __name__ == "__main__":
    main()
