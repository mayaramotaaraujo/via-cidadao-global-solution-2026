"""Gera os dados SINTÉTICOS do projeto (nenhum dado pessoal real).

1. dados/treino/relatos_rotulados.csv: base de treino do classificador, montada
   por combinação de trechos (problema + local + contexto). Semente fixa: o
   mesmo arquivo é gerado em qualquer máquina.
2. entrada/: lote de demonstração dos três canais (SP156 em CSV, subprefeitura
   em Excel e exportação do app Zelo em JSON), com erros de propósito para
   mostrar a quarentena: bairro inexistente, descrição vazia, data inválida,
   linha duplicada, e-mail inválido e dados pessoais no texto.

O conjunto de TESTE (dados/teste/casos_teste_rotulados.csv) foi escrito à mão,
separado deste gerador, para a métrica não ser inflada por frases repetidas.

Uso: python -m scripts.gerar_dados
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent

ABERTURAS = [
    "", "", "", "Bom dia, ", "Boa tarde. ", "Olá, ", "Gostaria de informar que ", "Venho reclamar: ",
    "Moro aqui há anos e ", "Por favor, ", "Socorro, ", "Oi prefeitura, ", "Preciso de ajuda: ",
    "Quero registrar que ", "Mais uma vez ",
]

LOCAIS = [
    "na minha rua", "em frente ao mercado", "perto da escola estadual", "na esquina da padaria",
    "na avenida principal do bairro", "perto do ponto de ônibus", "na rua de trás da igreja",
    "ao lado da praça", "em frente ao número 120", "na saída do metrô", "perto da UBS",
    "na rua da feira", "na viela que desce pro córrego", "no cruzamento perto do posto",
    "em frente à creche", "perto do campinho", "na calçada", "na calçada da escola",
    "na frente do prédio", "na calçada do mercado",
]

PROBLEMAS: dict[str, list[str]] = {
    "buraco_pavimentacao": [
        "tem um buraco enorme no asfalto", "abriu uma cratera no meio da rua", "o asfalto está todo esburacado",
        "tem um buraco fundo que enche de água", "o recapeamento soltou e virou buraco", "a rua está cheia de buracos",
        "tem um buraco que já estourou pneu de carro", "o asfalto afundou perto do bueiro",
        "a pavimentação está toda rachada e soltando pedra", "tem buraco na pista que os carros desviam",
        "o tapa-buraco que fizeram já abriu de novo", "tem uma valeta aberta no asfalto depois de uma obra",
        "a rua de paralelepípedo está toda solta", "os motoqueiros caem no buraco da curva",
        "tem um buraco gigante na faixa da direita", "burako enorme no asfalto",
    ],
    "iluminacao_publica": [
        "o poste está apagado", "a lâmpada do poste queimou", "a rua inteira está sem luz à noite",
        "o poste fica piscando a noite toda", "a luz do poste está acesa durante o dia",
        "três postes seguidos estão sem iluminação", "a luminária do poste está quebrada e pendurada",
        "a iluminação da praça não funciona", "o refletor da quadra está apagado",
        "o poste está com a lâmpada fraca e a rua fica um breu", "a rua fica escura porque o poste não acende",
        "faz semanas que o poste não acende", "poste apagadu ha dias", "a luz pública queimou de novo",
        "o poste tem fio desencapado e soltando faísca", "o fio do poste caiu no chão",
    ],
    "calcada_acessibilidade": [
        "a calçada está toda quebrada", "não tem rampa de acessibilidade na esquina", "a calçada está levantada pelas raízes",
        "o piso tátil está arrancado", "a calçada tem um degrau enorme", "tem um buraco na calçada",
        "a calçada é tão estreita que a gente anda na rua", "a rampa de cadeirante está quebrada",
        "o passeio está cheio de lajotas soltas", "a calçada afundou e virou um buraco",
        "não dá pra passar com carrinho de bebê na calçada", "a calçada está toda irregular e escorregadia",
        "colocaram entulho e a calçada ficou bloqueada", "a guia da calçada está quebrada",
        "cadeirante não consegue subir na calçada", "calsada toda esburacada",
    ],
    "alagamento_drenagem": [
        "o bueiro está entupido", "a rua alaga toda vez que chove", "a boca de lobo está cheia de lixo",
        "a água da chuva não escoa", "o córrego transbordou", "o bueiro está sem tampa",
        "a galeria pluvial está entupida e volta água", "quando chove forma um lago na esquina",
        "a enxurrada invade as casas", "o piscinão está cheio de mato e não drena",
        "o bueiro está exalando cheiro de esgoto e entupido", "a sarjeta fica empoçada dias depois da chuva",
        "a água chega na cintura quando chove", "a tampa do bueiro quebrou", "alagou tudo de novo com a chuva",
        "a boca de lobo entupida faz a rua virar rio",
    ],
    "lixo_entulho": [
        "jogaram entulho na calçada", "tem lixo acumulado há dias", "a coleta de lixo não passou essa semana",
        "descartaram um sofá velho na esquina", "o terreno baldio virou lixão", "tem restos de obra jogados na rua",
        "a caçamba de entulho está transbordando", "os sacos de lixo estão rasgados e espalhados",
        "tem pneus velhos jogados no canteiro", "despejaram móveis velhos na praça",
        "o lixo está atraindo ratos e baratas", "a lixeira da praça está quebrada e cheia",
        "o ponto viciado de lixo voltou", "jogam lixo no córrego toda noite", "tem colchão velho largado na calçada",
        "lixo espalhado pela rua toda",
    ],
    "arvore_poda": [
        "a árvore está com galhos encostando na fiação", "uma árvore caiu na rua", "a árvore está inclinada e ameaçando cair",
        "precisa podar a árvore que tampa o poste", "os galhos estão invadindo a janela", "a árvore está morta e seca",
        "um galho grande quebrou e está pendurado", "as raízes da árvore estão quebrando o muro",
        "a árvore caiu em cima de um carro", "a copa da árvore está cobrindo a placa de trânsito",
        "tem cupim na árvore e ela está oca", "pedido de poda da árvore em frente de casa",
        "o vento derrubou galhos na calçada", "a árvore está prestes a cair", "arvore enorme precisando de poda",
        "galho caindo em cima da fiação",
    ],
    "sinalizacao_transito": [
        "o semáforo está apagado", "o farol está quebrado e fica piscando", "a faixa de pedestre está apagada",
        "a placa de pare foi arrancada", "não tem sinalização na lombada", "a placa de rua caiu",
        "o semáforo de pedestre não abre", "falta faixa de pedestre perto da escola",
        "a pintura da pista sumiu", "a placa de velocidade está tampada", "o farol está desregulado e o verde dura segundos",
        "a lombada não tem pintura e ninguém vê", "a placa de sentido proibido está virada",
        "semaforo piscando amarelo o dia todo", "o semáforo do cruzamento está desligado",
        "precisamos de uma lombada e sinalização",
    ],
    "outros": [
        "o vizinho faz barulho todo dia de madrugada", "quero saber como pagar o IPTU atrasado",
        "o ônibus da linha não passa no horário", "quero marcar consulta no posto de saúde",
        "tem um cachorro abandonado na rua", "a internet do bairro está caindo", "quero parabenizar o atendimento",
        "como faço para tirar a segunda via da conta de água", "o bar fica com som alto até tarde",
        "quero informação sobre a vacina da gripe", "meu vizinho construiu sem alvará",
        "a fila do poupatempo está enorme", "quero me inscrever em curso da prefeitura",
        "o carro do vizinho está abandonado há meses na garagem dele", "quero saber o horário da feira",
        "o aplicativo do bilhete único não funciona",
    ],
}

COMPLEMENTOS = [
    "", "", "", "", ".", ". Já faz uma semana.", ". Faz mais de um mês.", ", ninguém resolve.",
    ". Já reclamei antes.", ". É perigoso.", ". Passa muita criança por aqui.", ". Meu pai é idoso e quase caiu.",
    ". À noite fica muito perigoso.", ". Não é urgente, mas seria bom ver.", ". Quando puder, por favor.",
    ". Teve um acidente ontem.", ". Uma senhora tropeçou semana passada.", ". Atrapalha todo mundo.",
    ". Obrigado.", "!!!", ". Pedimos providências.",
]


def gerar_treino(caminho: Path, por_categoria: int = 110, semente: int = 42) -> pd.DataFrame:
    rnd = random.Random(semente)
    linhas = []
    for categoria, problemas in PROBLEMAS.items():
        vistos: set[str] = set()
        tentativas = 0
        while len(vistos) < por_categoria and tentativas < por_categoria * 20:
            tentativas += 1
            problema = rnd.choice(problemas)
            local = rnd.choice(LOCAIS) if categoria != "outros" or rnd.random() < 0.3 else ""
            if categoria == "calcada_acessibilidade" and "calçada" in local:
                local = "na minha rua"
            frase = f"{rnd.choice(ABERTURAS)}{problema} {local}".strip() + rnd.choice(COMPLEMENTOS)
            if rnd.random() < 0.15:
                frase = frase.lower()
            frase = frase[0].upper() + frase[1:]
            if frase not in vistos:
                vistos.add(frase)
                linhas.append({"descricao": frase, "categoria": categoria})
    df = pd.DataFrame(linhas).sample(frac=1, random_state=semente).reset_index(drop=True)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(caminho, index=False)
    return df


# ---------------------------------------------------------------------------
# Lote de demonstração
# ---------------------------------------------------------------------------
SP156 = [
    # (id, bairro, descrição, e-mail, aceite)
    ("SP156-88231", "ITAQUERA", "FIO DO POSTE CAIDO NA CALCADA SOLTANDO FAISCA PERTO DO PONTO DE ONIBUS", "maria.silva@example.com", "S"),
    ("SP156-88232", "capao redondo", "Calçada em frente à UBS toda quebrada, minha mãe é cadeirante e tem que ir pela rua", "joao.p@example.com", "S"),
    ("SP156-88233", "TATUAPE", "Poste apagado na esquina há uma semana, a rua fica escura e muita gente volta do metrô a pé", "", "N"),
    ("SP156-88234", "LAPA", "Jogaram sacos de lixo e um sofá velho na esquina da praça, faz três dias", "ana@example.com", "S"),
    ("SP156-88235", "PENHA", "Buraco enorme na rua, quase caí de moto. Meu CPF 123.456.789-00, me liga (11) 98765-4321", "carlos.m@example.com", "S"),
    ("SP156-88236", "JARDIM DAS FLORES", "Árvore com galho encostando nos fios da rua", "x@example.com", "S"),  # bairro inexistente
    ("SP156-88237", "SE", "", "", "N"),  # descrição vazia
    ("SP156-88238", "MOOCA", "O semáforo do cruzamento da avenida está apagado desde cedo, quase teve batida em frente à escola", "", "N"),
    ("SP156-88239", "GRAJAU", "Quando chove a rua alaga inteira, o bueiro está entupido de lixo", "email-invalido", "S"),
    ("SP156-88240", "PINHEIROS", "Quero saber como faço para pagar o IPTU atrasado do meu apartamento", "pedro@example.com", "S"),
    ("SP156-88235", "PENHA", "Buraco enorme na rua, quase caí de moto. Meu CPF 123.456.789-00, me liga (11) 98765-4321", "carlos.m@example.com", "S"),  # duplicado
]

SUBPREF = [
    ("SUB-CL-0412", "Campo Limpo", "A árvore da rua está inclinada, com o tronco rachado, e parece que vai cair em cima das casas", "lucia@example.com", "Sim"),
    ("SUB-CL-0413", "Campo Limpo", "Pedido de poda da árvore em frente ao número 45, os galhos tampam a luz do poste. Não é urgente.", "", "Não"),
    ("SUB-CL-0414", "Jardim Ângela", "Entulho de obra jogado no canteiro central faz duas semanas, está juntando rato", "rafa@example.com", "Sim"),
    ("SUB-CL-0415", "Capão Redondo", "Faixa de pedestre em frente à creche totalmente apagada, os carros não param", "", "Não"),
    ("SUB-CL-0416", "Campo Limpo", "Rua alagada", "", "Não"),  # curta demais
    ("SUB-CL-0417", "Jardim Ângela", "Tem um negócio estranho na rua que ninguém sabe o que é, um cano aparecendo", "bia@example.com", "Sim"),
    ("SUB-CL-0418", "Campo Limpo", "O ônibus 6450 vive atrasado, ninguém respeita o horário e o motorista é grosso", "", "Não"),
]

APP = [
    {"protocolo": "ZL-2026-000141", "bairro": "Santana", "categoria": "buraco_pavimentacao", "urgencia": "media",
     "descricao_anonimizada": "Buraco no asfalto da rua lateral do terminal, os carros desviam pela contramão."},
    {"protocolo": "ZL-2026-000142", "bairro": "Vila Mariana", "categoria": "iluminacao_publica", "urgencia": "alta",
     "descricao_anonimizada": "Três postes apagados seguidos no caminho da estação, idosos evitam passar à noite."},
    {"protocolo": "ZL-2026-000143", "bairro": "Sapopemba", "categoria": "alagamento_drenagem", "urgencia": "media",
     "descricao_anonimizada": "Boca de lobo entupida de folhas, a água da chuva fica empoçada na frente da escola."},
    {"protocolo": "ZL-2026-000144", "bairro": "Bairro Inventado", "categoria": "lixo_entulho", "urgencia": "baixa",
     "descricao_anonimizada": "Lixo acumulado na esquina."},  # bairro inválido
]


def gerar_lote_demo(pasta: Path, semente: int = 7) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in list(pasta.glob("sp156_*.csv")) + list(pasta.glob("subprefeitura_*.xlsx")) + list(pasta.glob("app_zelo_*.json")):
        antigo.unlink()
    rnd = random.Random(semente)
    hoje = datetime.now().replace(second=0, microsecond=0)
    dia = hoje.strftime("%Y%m%d")

    def quando() -> datetime:
        return hoje - timedelta(hours=rnd.randint(1, 20), minutes=rnd.randint(0, 59))

    sp = pd.DataFrame([{
        "NUM_SOLICITACAO": i, "DATA_ABERTURA": quando().strftime("%d/%m/%Y %H:%M"), "DISTRITO": b,
        "DESCRICAO_SOLICITACAO": d, "EMAIL_CONTATO": e, "ACEITE_CONTATO": a,
    } for i, b, d, e, a in SP156])
    sp.loc[sp["NUM_SOLICITACAO"] == "SP156-88238", "DATA_ABERTURA"] = "31/02/2026 25:99"  # data inválida
    sp.loc[sp.index[-1], "DATA_ABERTURA"] = sp.loc[4, "DATA_ABERTURA"]  # duplicata idêntica
    arq_sp = pasta / f"sp156_{dia}.csv"
    sp.to_csv(arq_sp, sep=";", index=False, encoding="utf-8")

    sub = pd.DataFrame([{
        "Nº": i, "Data": quando(), "Bairro": b, "Relato do munícipe": d, "E-mail": e, "Autoriza contato?": a,
    } for i, b, d, e, a in SUBPREF])
    arq_sub = pasta / f"subprefeitura_campo_limpo_{dia}.xlsx"
    sub.to_excel(arq_sub, index=False)

    app = [{**r, "criado_em": (quando()).isoformat() + "-03:00", "status": "recebido"} for r in APP]
    arq_app = pasta / f"app_zelo_{dia}.json"
    arq_app.write_text(json.dumps(app, ensure_ascii=False, indent=2), encoding="utf-8")
    return [arq_sp, arq_sub, arq_app]


if __name__ == "__main__":
    df = gerar_treino(RAIZ / "dados" / "treino" / "relatos_rotulados.csv")
    print(f"Base de treino: {len(df)} exemplos\n{df['categoria'].value_counts().to_string()}")
    for a in gerar_lote_demo(RAIZ / "entrada"):
        print(f"Lote de demonstração: {a.relative_to(RAIZ)}")
