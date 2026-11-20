"""Teste ponta a ponta: 10 conversas com 3 turnos cada, passando por
áudio -> STT -> RAG -> LLM -> adaptação -> TTS, com latência por etapa.

Entrada de áudio de cada turno:
  * se existir material_teste/e2e/audios/<conversa>_t<turno>.(wav|m4a|mp3...), usa a gravação real;
  * senão, gera a fala do "cidadão" com uma voz sintética diferente
    (pt-BR-AntonioNeural) só para simular a entrada. Esse tempo NÃO entra na latência.

Uso:
    python -m eval.eval_e2e
Saídas: results/e2e_turnos.csv e results/e2e_resumo.csv
"""
from __future__ import annotations

import csv
from collections import OrderedDict

from eval.common import MATERIAL, RESULTS, describe, find_audio
from zelo.config import settings
from zelo.latency import STAGES
from zelo.llm import build_llm
from zelo.pipeline import Conversation, VoicePipeline
from zelo.privacy import secure_delete
from zelo.stt import WhisperSTT
from zelo.tts import EdgeTTS, build_tts


def main() -> None:
    e2e_dir = MATERIAL / "e2e"
    turns = list(csv.DictReader(open(e2e_dir / "conversas.csv", encoding="utf-8")))
    convs: "OrderedDict[str, list[dict]]" = OrderedDict()
    for t in turns:
        convs.setdefault(t["conversa"], []).append(t)

    stt = WhisperSTT()
    print(f"Carregando {stt.name}...")
    stt.warmup()
    pipe = VoicePipeline(stt=stt, llm=build_llm(), tts=build_tts())
    citizen_voice = EdgeTTS(voice="pt-BR-AntonioNeural", rate="+0%")

    rows = []
    for conv_id, ts in convs.items():
        conv = Conversation()
        print(f"\n=== Conversa {conv_id} ===")
        for t in ts:
            recorded = find_audio(e2e_dir / "audios", f"{conv_id}_t{t['turno']}.wav")
            if recorded:
                audio, origem = str(recorded), "gravado"
            else:
                audio = citizen_voice.synthesize(t["fala"], settings.tmp_audio_dir / f"in_{conv_id}_{t['turno']}.mp3").audio_path
                origem = "sintetico"
            res = pipe.run_audio(audio, conv, delete_audio=(origem == "sintetico"), source="e2e")
            if res.audio_path:
                secure_delete(res.audio_path)
            row = {"conversa": conv_id, "turno": t["turno"], "entrada": origem, "fala_esperada": t["fala"],
                   "transcricao": res.transcript, "resposta": res.answer, "texto_falado": res.spoken_text}
            row.update({f"{s}_s": round(res.timer.times.get(s, 0), 3) for s in STAGES})
            row["total_s"] = round(res.timer.total, 3)
            rows.append(row)
            print(f"T{t['turno']} [{res.timer.summary()}]\n  cidadão: {res.transcript}\n  Zelo:    {res.answer}")

    with open(RESULTS / "e2e_turnos.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    resumo = []
    for s in [*STAGES, "total"]:
        d = describe([r[f"{s}_s"] for r in rows])
        resumo.append({"etapa": s, **d})
    with open(RESULTS / "e2e_resumo.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(resumo[0].keys()))
        w.writeheader()
        w.writerows(resumo)

    print("\n=== LATÊNCIA PONTA A PONTA (s) ===")
    for r in resumo:
        print(f"{r['etapa']:>6}: média {r['media']:.2f} | mediana {r['mediana']:.2f} | p90 {r['p90']:.2f}")
    print(f"\n{len(rows)} turnos em {len(convs)} conversas. Arquivos em {RESULTS}")


if __name__ == "__main__":
    main()
