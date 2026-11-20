"""Proteções do assistente: injeção de prompt, dados pessoais, emergência e
checagem se a resposta tem apoio nas fontes."""
import re

from retriever import normalizar

# Frases típicas de quem tenta desviar o assistente (comparadas sem acento e em minúsculas)
PADROES_INJECAO = [
    r"ignore (todas? )?(as |os )?(instrucoes|regras|ordens|comandos)",
    r"ignore tudo",
    r"esqueca (as |tudo|suas )",
    r"(revele|mostre|diga|exiba|repita) (o |seu |as |suas )*(prompt|instrucoes|regras internas|configuracao)",
    r"system prompt",
    r"prompt do sistema",
    r"voce (agora )?e (um|uma) ",
    r"finja (que )?(ser|e|voce)",
    r"modo (desenvolvedor|deus|admin)",
    r"desconsidere (as |o )?(regras|instrucoes|contexto)",
    r"a partir de agora (voce|responda|ignore)",
]

PADROES_PII = {
    "cpf": r"\b\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}\b",
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "celular": r"(?<!\d)(?:\+?55\s?)?\(?\d{2}\)?\s?9\d{4}[-\s]?\d{4}(?!\d)",
}

PALAVRAS_EMERGENCIA = [
    "fio partido", "fio solto", "fio caido", "faisca", "choque eletrico", "poste caiu",
    "poste caido", "poste caindo", "prestes a cair", "desabamento", "desabou", "arvore caiu",
    "alagamento com pessoas", "pessoa ferida", "incendio", "vazamento de gas",
]

AVISO_EMERGENCIA = (
    "Atenção: o que você descreveu pode ser uma situação de risco. Afaste as pessoas do local "
    "e ligue agora para os serviços de emergência: Bombeiros 193, Defesa Civil 199 ou SAMU 192. "
    "Este aviso é padrão do sistema e não vem das fontes consultadas."
)


def tem_injecao(texto):
    t = normalizar(texto)
    return any(re.search(p, t) for p in PADROES_INJECAO)


def mascarar_dados_pessoais(texto):
    """Troca CPF, e-mail e celular por marcas. Devolve (texto_limpo, tipos_encontrados)."""
    achados = []
    saida = texto
    for tipo, padrao in PADROES_PII.items():
        if re.search(padrao, saida):
            achados.append(tipo)
            saida = re.sub(padrao, f"[{tipo} removido]", saida)
    return saida, achados


def detectar_emergencia(texto):
    t = normalizar(texto)
    return any(p in t for p in PALAVRAS_EMERGENCIA)


def trecho_suspeito(texto_do_trecho):
    """Injeção indireta: documento que traz ordens para o assistente."""
    return tem_injecao(texto_do_trecho)


def _numeros(texto):
    return {re.sub(r"\D", "", n) for n in re.findall(r"\d[\d .\-/]{1,}\d", texto) if len(re.sub(r"\D", "", n)) >= 2}


def numeros_sem_apoio(resposta, trechos):
    """Telefones, prazos e outros números que aparecem na resposta mas não estão nos trechos usados."""
    base = " ".join(t["texto"] for t in trechos)
    num_base = _numeros(base)
    # números soltos como "24" e "156" também contam
    soltos_base = set(re.findall(r"\d+", base))
    faltando = []
    for n in _numeros(resposta):
        if n not in num_base and not all(p in soltos_base for p in re.findall(r"\d+", n)):
            faltando.append(n)
    return faltando
