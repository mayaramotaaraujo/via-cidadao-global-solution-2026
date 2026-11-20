"""Teste do processamento de sequência e vídeo com dados falsos (só confere se roda)."""
import sys
import tempfile
from pathlib import Path

import cv2
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from modelo import criar_modelo  # noqa: E402
from ocorrencia import montar_ocorrencia  # noqa: E402
from sintetico import criar_sequencia_falsa  # noqa: E402
from video import analisar_imagem, processar_video  # noqa: E402

tmp = Path(tempfile.mkdtemp())
seq = criar_sequencia_falsa(tmp / "seq")
m = criar_modelo("mobilenet_v3_small", pesos=False).eval()
disp = torch.device("cpu")

img, r = analisar_imagem(m, seq / "quadro_005.jpg", 0.5, 128, disp)
assert img.shape[0] > 0 and r["recortes"] == 8, r
print("imagem ok:", r)

res = processar_video(m, seq, tmp / "saida.mp4", tmp / "saida.json", 0.5, 128, disp, cada_n=1)
assert res["quadros_analisados"] == 12 and (tmp / "saida.mp4").stat().st_size > 0
print("sequência ok:", {k: v for k, v in res.items() if k != "quadros"})

# vídeo de verdade (mp4) a partir da sequência
v = tmp / "entrada.mp4"
w = cv2.VideoWriter(str(v), cv2.VideoWriter_fourcc(*"mp4v"), 10, (1024, 512))
for p in sorted(seq.glob("*.jpg")):
    w.write(cv2.imread(str(p)))
w.release()
res2 = processar_video(m, v, tmp / "saida2.mp4", None, 0.5, 128, disp, cada_n=2)
assert res2["quadros_analisados"] == 6
print("vídeo ok:", res2["quadros_analisados"], "quadros")

oc = montar_ocorrencia(0.8, 0.5, "teste")
assert oc["triagem"] == "encaminhar_para_inspecao" and "aviso" in oc
print("ocorrência ok:", oc["id"])
