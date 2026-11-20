"""Ligação com o resto do VIA CIDADÃO.

Recebe uma ocorrência no formato combinado entre as disciplinas (o mesmo JSON do banco)
e devolve a orientação do assistente para o cidadão. Assim o assistente não fica solto:
ele lê o que o módulo de visão, o de zeladoria ou o de som já registraram.
"""
from pipeline import Assistente

PERGUNTA_POR_CATEGORIA = {
    "buraco": "Como peço o conserto de um buraco na rua no SP156?",
    "poste_apagado": "Como peço conserto de poste com luz apagada?",
    "dano_calcada": "O que diz a lei sobre barreiras urbanísticas em calçadas?",
    "calcada_sem_rampa": "O que diz a lei sobre barreiras urbanísticas em calçadas?",
    "bueiro_entupido": "Como solicito limpeza de bueiro, boca de lobo ou poço de visita?",
}


def orientar_ocorrencia(ocorrencia, assistente=None):
    """ocorrencia: dict com pelo menos 'id' e 'categoria' (contrato do projeto)."""
    assistente = assistente or Assistente()
    pergunta = PERGUNTA_POR_CATEGORIA.get(
        ocorrencia.get("categoria", ""), "Como faço para registrar um problema urbano?")
    r = assistente.responder(pergunta)
    return {"ocorrencia_id": ocorrencia.get("id"), "pergunta_usada": pergunta,
            "status": r["status"], "orientacao": r["resposta"]}


if __name__ == "__main__":
    exemplo = {"id": "VIA-0001", "categoria": "poste_apagado", "status": "aguardando_validacao"}
    print(orientar_ocorrencia(exemplo)["orientacao"])
