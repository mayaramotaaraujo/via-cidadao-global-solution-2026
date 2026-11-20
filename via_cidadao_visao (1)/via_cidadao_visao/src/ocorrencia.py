"""Ocorrência do VIA VISÃO no formato que os outros módulos do VIA CIDADÃO leem."""
import uuid
from datetime import datetime

AVISO = ("A presença de fissura na imagem não indica a gravidade nem a segurança estrutural. "
         "Este resultado serve só para decidir o que um profissional deve inspecionar primeiro.")


def nivel_triagem(prob_max, limiar):
    """Três faixas de triagem. As faixas são uma escolha de projeto, não foram validadas em campo."""
    if prob_max >= limiar:
        return "encaminhar_para_inspecao"
    if prob_max >= limiar / 2:
        return "revisao_humana"
    return "sem_indicio"


def montar_ocorrencia(prob_max, limiar, origem, n_recortes=1, n_recortes_positivos=0,
                      latitude=None, longitude=None, extra=None):
    nivel = nivel_triagem(prob_max, limiar)
    oc = {
        "id": "VIA-VISAO-" + uuid.uuid4().hex[:8].upper(),
        "modulo": "VIA VISAO",
        "categoria": "fissura_em_superficie" if nivel != "sem_indicio" else "sem_indicio",
        "confianca_modelo": round(float(prob_max), 4),
        "limiar_usado": float(limiar),
        "triagem": nivel,
        "recortes_analisados": int(n_recortes),
        "recortes_com_fissura": int(n_recortes_positivos),
        "origem": origem,
        "localizacao": {"latitude": latitude, "longitude": longitude},
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "aviso": AVISO,
    }
    if extra:
        oc.update(extra)
    return oc
