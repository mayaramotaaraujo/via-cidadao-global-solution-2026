"""Pipeline completo do assistente VIA CIDADÃO:
pergunta, proteções de entrada, busca, filtro de trechos, decisão de responder ou
se abster, geração, checagem final e formatação com fontes."""
from pathlib import Path

from chunking import CONFIGS, carregar_corpus
from gerador import gerar
from protecoes import (AVISO_EMERGENCIA, detectar_emergencia, mascarar_dados_pessoais,
                       numeros_sem_apoio, tem_injecao, trecho_suspeito)
from retriever import Buscador, tokens

PASTA_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus"

MSG_SEM_RESPOSTA = ("Não encontrei essa informação nas fontes que tenho. "
                    "Se você mora em São Paulo, o canal oficial para tirar essa dúvida é o 156.")
MSG_BLOQUEIO = ("Não posso fazer isso. Eu só ajudo a explicar como pedir serviços da prefeitura "
                "e quais são as regras de acessibilidade, com base nas fontes cadastradas.")
MSG_ESCLARECER = ("Pode me contar mais? Diga qual é o problema (por exemplo buraco, poste apagado, "
                  "calçada sem rampa ou bueiro entupido) e em que cidade ele está.")

LIMIAR_COBERTURA = 0.30   # escolhido no conjunto de desenvolvimento (varredura em avaliar.py)
TOP_K_PADRAO = 5          # na primeira rodada era 3, ver relatório
MIN_TOKENS_PERGUNTA = 2   # na primeira rodada era 3, e barrou uma pergunta válida
MIN_TERMOS_EM_COMUM = 2


class Assistente:
    def __init__(self, config="C_estrutural_700_overlap_1frase", modo_busca="hibrido",
                 top_k=TOP_K_PADRAO, modo_geracao="extrativo", pasta_corpus=PASTA_CORPUS,
                 limiar=LIMIAR_COBERTURA):
        self.chunks = carregar_corpus(pasta_corpus, CONFIGS[config])
        self.buscador = Buscador(self.chunks, modo=modo_busca)
        self.top_k = top_k
        self.modo_geracao = modo_geracao
        self.limiar = limiar

    def responder(self, pergunta, historico=None):
        saida = {"pergunta_original": pergunta, "status": None, "resposta": "", "trechos": [],
                 "removidos_por_suspeita": [], "avisos": []}

        # 1. injeção direta
        if tem_injecao(pergunta):
            saida.update(status="bloqueada", resposta=MSG_BLOQUEIO)
            return saida

        # 2. dados pessoais saem da pergunta antes de qualquer outra etapa
        limpa, achados = mascarar_dados_pessoais(pergunta)
        if achados:
            saida["avisos"].append("Removi dados pessoais da sua mensagem (" + ", ".join(achados)
                                   + "). Não é preciso informar isso aqui.")

        # 3. pergunta curta usa a pergunta anterior como contexto
        consulta = limpa
        if len(tokens(limpa)) < MIN_TOKENS_PERGUNTA and historico:
            consulta = historico[-1] + " " + limpa
        elif len(tokens(limpa)) < MIN_TOKENS_PERGUNTA:
            saida.update(status="esclarecer", resposta=MSG_ESCLARECER)
            self._juntar_avisos(saida)
            return saida

        # 4. emergência
        emergencia = detectar_emergencia(consulta)
        if emergencia:
            saida["avisos"].insert(0, AVISO_EMERGENCIA)

        # 5. busca e filtro de trechos com ordens escondidas
        achados_busca = self.buscador.buscar(consulta, top_k=self.top_k + 2)
        seguros = []
        for t in achados_busca:
            if trecho_suspeito(t["texto"]):
                saida["removidos_por_suspeita"].append(t["id"])
            else:
                seguros.append(t)
        trechos = seguros[: self.top_k]
        saida["trechos"] = trechos

        # 6. decide se tem base para responder
        if not trechos:
            saida.update(status="abstencao", resposta=MSG_SEM_RESPOSTA)
            self._juntar_avisos(saida)
            return saida
        melhor = trechos[0]
        cobertura = self.buscador.cobertura(consulta, melhor)
        termos_comuns = round(cobertura * len(set(tokens(consulta))))
        saida["cobertura_melhor"] = round(cobertura, 2)
        if cobertura < self.limiar or termos_comuns < MIN_TERMOS_EM_COMUM:
            saida.update(status="abstencao", resposta=MSG_SEM_RESPOSTA)
            self._juntar_avisos(saida)
            return saida

        # 7. gera e confere
        texto = gerar(consulta, trechos, self.modo_geracao)
        if not texto:
            saida.update(status="abstencao", resposta=MSG_SEM_RESPOSTA)
            self._juntar_avisos(saida)
            return saida
        sem_apoio = numeros_sem_apoio(texto, trechos)
        if sem_apoio:
            saida["avisos"].append("Resposta trocada por abstenção: números sem apoio nas fontes " + str(sem_apoio))
            saida.update(status="abstencao", resposta=MSG_SEM_RESPOSTA)
            self._juntar_avisos(saida)
            return saida

        usados = []
        for t in trechos:
            if f"[{t['doc_id']}]" in texto and t["doc_id"] not in [u["doc_id"] for u in usados]:
                usados.append(t)
        fontes = "\n".join(f"[{u['doc_id']}] {u['titulo_doc']}. {u['url']} (consultado em {u['consulta']})"
                           for u in usados)
        saida.update(status="emergencia" if emergencia else "respondida",
                     resposta=texto + ("\n\nFontes:\n" + fontes if fontes else ""))
        self._juntar_avisos(saida)
        return saida

    @staticmethod
    def _juntar_avisos(saida):
        if saida["avisos"]:
            saida["resposta"] = "\n".join(saida["avisos"]) + "\n\n" + saida["resposta"]
