"""Tela do VIA VISÃO (Streamlit): recebe imagem ou vídeo e mostra onde há possível fissura.

Rodar na raiz do projeto:  streamlit run app/triagem.py
Precisa do arquivo results/modelo.pt, gerado por src/treinar.py.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402
import torch  # noqa: E402

from ocorrencia import montar_ocorrencia  # noqa: E402
from video import analisar_imagem, carregar_checkpoint, processar_video  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_MODELO = RAIZ / "results" / "modelo.pt"

st.set_page_config(page_title="VIA VISÃO", page_icon="🔎", layout="wide")


@st.cache_resource
def carregar():
    disp = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    m, ck = carregar_checkpoint(CAMINHO_MODELO, disp)
    return m, ck, disp


st.title("VIA VISÃO: triagem de fissuras")
st.caption("Envie uma foto, uma sequência de fotos ou um vídeo curto de uma superfície (pavimento, parede, ponte). "
           "O resultado ajuda a decidir o que um profissional deve inspecionar primeiro. "
           "Ele não mede a gravidade nem diz se a estrutura é segura.")

if not CAMINHO_MODELO.exists():
    st.error("Não achei results/modelo.pt. Rode primeiro: python src/treinar.py --raiz CAMINHO_DA_SDNET2018")
    st.stop()

modelo, ck, disp = carregar()

with st.sidebar:
    st.subheader("Configuração")
    st.write(f"Modelo: **{ck['arquitetura']}**, entrada {ck['tamanho']}x{ck['tamanho']}, dispositivo **{disp}**")
    limiar = st.slider("Limiar de confiança", 0.05, 0.95, float(ck["limiar"]), 0.01,
                       help="O valor padrão foi escolhido na validação. Limiar menor acusa mais fissuras e "
                            "gera mais alarmes falsos. Limiar maior deixa passar mais fissuras.")
    largura = st.select_slider("Largura de análise (px)", options=[512, 768, 1024, 1536], value=1024,
                               help="Mais largura corta mais recortes e demora mais.")
    st.caption("Acima do limiar: marcado em vermelho. Entre metade do limiar e o limiar: revisão humana.")

aba_img, aba_vid = st.tabs(["Imagem", "Vídeo ou sequência"])

with aba_img:
    arq = st.file_uploader("Foto da superfície", type=["jpg", "jpeg", "png"], key="img")
    if arq:
        dados = np.frombuffer(arq.read(), dtype=np.uint8)
        quadro = cv2.imdecode(dados, cv2.IMREAD_COLOR)
        if quadro is None:
            st.error("Não consegui ler essa imagem.")
        else:
            desenhada, r = analisar_imagem(modelo, quadro, limiar, ck["tamanho"], disp, largura)
            c1, c2 = st.columns([3, 2])
            c1.image(cv2.cvtColor(desenhada, cv2.COLOR_BGR2RGB), use_container_width=True)
            oc = montar_ocorrencia(r["prob_max"], limiar, f"imagem:{arq.name}", r["recortes"],
                                   r["recortes_positivos"])
            c2.metric("Confiança máxima", f"{r['prob_max']:.2f}")
            c2.metric("Recortes com possível fissura", f"{r['recortes_positivos']} de {r['recortes']}")
            c2.metric("Tempo de análise", f"{r['ms']:.0f} ms")
            c2.write(f"Triagem: **{oc['triagem'].replace('_', ' ')}**")
            c2.caption(oc["aviso"])
            with c2.expander("Ocorrência em JSON (enviada ao VIA ZELADORIA)"):
                st.json(oc)

with aba_vid:
    st.write("Vídeo curto (mp4, mov, avi) para simular o monitoramento urbano. "
             "Um alerta só é confirmado quando 2 quadros analisados seguidos passam do limiar.")
    vid = st.file_uploader("Vídeo", type=["mp4", "mov", "avi"], key="vid")
    cada_n = st.number_input("Analisar 1 a cada quantos quadros", 1, 60, 5)
    limite = st.number_input("Máximo de quadros analisados", 5, 300, 60)
    if vid and st.button("Processar vídeo"):
        pasta = Path(tempfile.mkdtemp())
        entrada = pasta / vid.name
        entrada.write_bytes(vid.read())
        with st.spinner("Processando..."):
            res = processar_video(modelo, entrada, pasta / "saida.mp4", pasta / "saida.json", limiar,
                                  ck["tamanho"], disp, cada_n=int(cada_n), largura_alvo=largura,
                                  max_quadros=int(limite))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Quadros analisados", res["quadros_analisados"])
        c2.metric("Quadros com possível fissura", res["quadros_positivos"])
        c3.metric("Eventos confirmados", res["eventos_confirmados"])
        c4.metric("Tempo por quadro", f"{res['ms_medio_por_quadro']} ms" if res["ms_medio_por_quadro"] else "-")
        # O mp4 do OpenCV (mp4v) nem sempre toca no navegador, por isso também mostro o quadro mais confiante.
        st.video(str(pasta / "saida.mp4"))
        if res["quadros"]:
            st.line_chart({"confiança máxima por quadro": [q["prob_max"] for q in res["quadros"]]})
        st.download_button("Baixar resultado em JSON", json.dumps(res, ensure_ascii=False, indent=2),
                           file_name="resultado_video.json", mime="application/json")
