"""Monta o relatório do VIA VISÃO a partir dos números medidos em results/.

Nenhum número do relatório é digitado à mão: tudo vem de results/metricas.json,
results/dados.json e, se existir, results/video_resumo.json. Se rodar de novo o
treino, basta rodar este arquivo outra vez.

Uso:  python src/gerar_relatorio.py [pasta_results] [arquivo_saida]
"""
import json
import sys
from pathlib import Path


def v(x, casas=3):
    """Número com vírgula, como no português."""
    return f"{x:.{casas}f}".replace(".", ",")


def pc(x):
    return f"{x * 100:.1f}".replace(".", ",") + "%"


def tabela(cabecalho, linhas):
    out = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join(["---"] * len(cabecalho)) + "|"]
    out += ["| " + " | ".join(str(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)


NOMES = {"mobilenet_v3_small": "MobileNetV3 small", "resnet18": "ResNet18"}
SUP = {"D": "tabuleiros de ponte", "P": "pavimentos", "W": "paredes"}


def main():
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results")
    destino = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("docs/relatorio_visao.md")
    met = json.loads((pasta / "metricas.json").read_text(encoding="utf-8"))
    dad = json.loads((pasta / "dados.json").read_text(encoding="utf-8"))
    vid_arq = pasta / "video_resumo.json"
    vid = json.loads(vid_arq.read_text(encoding="utf-8")) if vid_arq.exists() else None

    mods = met["modelos"]
    esc = met["modelo_escolhido"]
    R = mods[esc]
    teste = R["teste_limiar_escolhido"]
    L = []
    add = L.append

    add("# VIA VISÃO: relatório de Visão Computacional\n")
    add("Projeto VIA CIDADÃO, Global Solution 2026.2, desafio CitizenTech.\n")
    add("Integrantes (nome completo e RM):\n* Mayara Mota, RM 563887\n* Gabriel Palmeira, RM 563522\n")
    if met["sintetico"] or met["sem_pesos_imagenet"]:
        add("> ATENÇÃO: estes números vêm de um teste com dados falsos ou sem pesos da ImageNet. "
            "Eles só provam que o código roda e NÃO podem ser entregues. Rode o treino com a base real.\n")

    add("## 1. Problema escolhido\n")
    add("Escolhemos o problema de identificar fissuras em concreto, tratado como classificação de imagens com duas classes: "
        "com fissura e sem fissura. Ele faz parte do módulo VIA VISÃO do projeto VIA CIDADÃO, que ajuda a zeladoria urbana "
        "a decidir o que inspecionar primeiro em pavimentos, paredes e pontes. O sistema é uma triagem para inspeção. "
        "A presença de fissura na imagem não diz se ela é grave nem se a estrutura é segura, e por isso o resultado "
        "sempre sai com esse aviso e com a indicação de revisão humana.\n")

    add("## 2. Base de dados e preparação\n")
    bc = dad["base_completa"]
    add(f"Usamos a SDNET2018, com {bc['recortes']} recortes de 256 por 256 pixels, vindos de {bc['fotos']} fotos de origem, "
        f"dos quais {bc['com_fissura']} têm fissura ({pc(bc['com_fissura'] / bc['recortes'])}). A base tem três tipos de superfície: "
        "tabuleiros de ponte (D), pavimentos (P) e paredes (W). Escolhemos essa base e não a Concrete Crack Images porque ela tem mais "
        "variedade visual (sombras, texturas, manchas, obstáculos) e porque o nome dos arquivos permite saber de qual foto cada "
        "recorte saiu, o que é necessário para dividir os dados sem vazamento. Na outra base nós não conseguimos confirmar essa informação.\n")
    add("A divisão em treino, validação e teste foi feita por foto de origem, em cada superfície, na proporção de 70, 15 e 15 por cento. "
        "Assim, todos os recortes de uma mesma foto ficam no mesmo conjunto. Nós confirmamos por código que nenhuma foto aparece em dois conjuntos. "
        "Se tivéssemos sorteado os recortes soltos, recortes vizinhos e quase iguais iriam para conjuntos diferentes e o resultado ficaria bom demais.\n")
    add("A tabela abaixo mostra o que foi usado. Como a atividade tem limite de 4 horas, reduzimos o treino: ficaram todos os recortes "
        "com fissura sorteados e o dobro de recortes sem fissura. A validação e o teste mantêm a proporção natural da base, para que precisão "
        "e revocação mostrem o que aconteceria no uso real.\n")
    linhas = []
    for c in ("treino", "validacao", "teste"):
        u = dad["usado"][c]
        linhas.append([c.replace("validacao", "validação"), u["fotos"], u["recortes"], u["com_fissura"], u["sem_fissura"],
                       pc(u["proporcao_fissura"])])
    add(tabela(["Conjunto", "Fotos de origem", "Recortes", "Com fissura", "Sem fissura", "Proporção com fissura"], linhas))
    add("\nPreparação das imagens: cada recorte é redimensionado para "
        f"{met['tamanho_entrada']} por {met['tamanho_entrada']} pixels e normalizado com a média e o desvio da ImageNet, "
        "porque as redes foram pré treinadas nessa base. No treino também aplicamos espelhamento horizontal e vertical e uma variação "
        "de brilho e contraste, para o modelo não depender tanto de sombra e iluminação.\n")

    add("## 3. Modelos e justificativa\n")
    add("Usamos transferência de aprendizado: pegamos redes já treinadas na ImageNet e trocamos apenas a última camada para duas classes. "
        "Comparamos duas redes pequenas, a MobileNetV3 small, pensada para celular e equipamentos simples, e a ResNet18, maior e em geral mais precisa. "
        f"O treino foi de {met['epocas']} épocas, com lote de {met['lote']}, otimizador AdamW e perda com peso maior para a classe com fissura, "
        "porque ela é a classe rara. Em cada época o modelo é avaliado na validação e fica guardado o estado com o melhor F1.\n")
    linhas = []
    for n, r in mods.items():
        linhas.append([NOMES.get(n, n), f"{r['parametros'] / 1e6:.2f} milhões".replace(".", ","),
                       v(r["validacao"]["f1"]), v(r["teste_limiar_escolhido"]["f1"]), f"{r['latencia']['ms_por_imagem']:.1f}".replace(".", ",")])
    add(tabela(["Modelo", "Parâmetros", "F1 na validação", "F1 no teste", "Tempo por imagem (ms)"], linhas))
    nomes = list(mods)
    if len(nomes) == 2:
        a, b = nomes
        mais_rapido = a if mods[a]["latencia"]["ms_por_imagem"] <= mods[b]["latencia"]["ms_por_imagem"] else b
        mais_f1 = a if mods[a]["validacao"]["f1"] >= mods[b]["validacao"]["f1"] else b
        if mais_rapido == mais_f1:
            add(f"\nA {NOMES[mais_f1]} foi melhor em F1 na validação e também mais rápida, então a escolha foi simples.")
        else:
            add(f"\nA {NOMES[mais_f1]} teve o melhor F1 na validação, enquanto a {NOMES[mais_rapido]} foi mais rápida. "
                "Escolhemos pelo F1 na validação, porque o objetivo é não deixar passar fissura, e mostro o custo de tempo na seção 6.")
    add(f"\nO modelo escolhido foi a **{NOMES.get(esc, esc)}**, pelo critério: {met['criterio_escolha']}. "
        "O teste não entrou nessa escolha.")
    if len(nomes) == 2:
        f1a = mods[nomes[0]]["teste_limiar_escolhido"]["f1"]
        f1b = mods[nomes[1]]["teste_limiar_escolhido"]["f1"]
        if abs(f1a - f1b) < 0.03:
            add(f"\nNa prática, a diferença entre os dois modelos no teste foi pequena (F1 {v(f1a)} e {v(f1b)}). "
                f"Como o teste tem só {dad['usado']['teste']['fotos']} fotos de origem, não dá para afirmar que um é melhor que o outro, "
                "e a escolha pela validação foi um critério de desempate.")
    if (pasta / "notas_limites.md").exists():
        add("A variação entre rodadas do mesmo treino está descrita na seção 9.")
    add("")

    add("## 4. Resultados no conjunto de teste\n")
    add(f"Com o limiar {v(R['limiar_escolhido'], 2)}, o modelo escolhido teve no teste:\n")
    add(tabela(["Precisão", "Revocação", "F1", "Acurácia", "AUC ROC", "Precisão média"],
               [[v(teste["precisao"]), v(teste["revocacao"]), v(teste["f1"]), v(teste["acuracia"]),
                 v(R["teste_curvas"]["auc_roc"]) if R["teste_curvas"]["auc_roc"] is not None else "n/d",
                 v(R["teste_curvas"]["precisao_media"]) if R["teste_curvas"]["precisao_media"] is not None else "n/d"]]))
    add("\nMatriz de confusão (linhas são a classe real, colunas são o que o modelo previu):\n")
    add(tabela(["", "Previu sem fissura", "Previu com fissura"],
               [["Real sem fissura", teste["tn"], teste["fp"]], ["Real com fissura", teste["fn"], teste["tp"]]]))
    add(f"\nO teste tem {teste['n']} recortes, dos quais {teste['positivos']} têm fissura. "
        "Como a classe com fissura é bem menos frequente, a acurácia sozinha engana: um modelo que sempre dissesse sem fissura "
        f"teria acurácia de {pc(1 - teste['positivos'] / teste['n'])}. Por isso olhamos principalmente a revocação, que mostra quantas fissuras "
        "reais foram achadas, e a precisão, que mostra quantos alarmes estavam certos.\n")

    add("Resultado por tipo de superfície:\n")
    linhas = []
    for s, m in sorted(R["teste_por_superficie"].items()):
        linhas.append([f"{s} ({SUP.get(s, s)})", m["n"], m["positivos"], v(m["precisao"]), v(m["revocacao"]), v(m["f1"])])
    add(tabela(["Superfície", "Recortes", "Com fissura", "Precisão", "Revocação", "F1"], linhas))
    com_pos = {s: m for s, m in R["teste_por_superficie"].items() if m["positivos"] > 0}
    if len(com_pos) >= 2:
        pior = min(com_pos, key=lambda s: com_pos[s]["revocacao"])
        melhor = max(com_pos, key=lambda s: com_pos[s]["revocacao"])
        add(f"\nA revocação foi maior em {SUP.get(melhor, melhor)} ({v(com_pos[melhor]['revocacao'])}) e menor em "
            f"{SUP.get(pior, pior)} ({v(com_pos[pior]['revocacao'])}). Os números por superfície têm poucas fissuras em alguns casos, "
            "então a diferença pode ser em parte sorte da divisão.")
        pm = min(com_pos, key=lambda s: com_pos[s]["precisao"])
        pM = max(com_pos, key=lambda s: com_pos[s]["precisao"])
        add(f"\nA precisão foi menor em {SUP.get(pm, pm)} ({v(com_pos[pm]['precisao'])}) e maior em {SUP.get(pM, pM)} ({v(com_pos[pM]['precisao'])}). "
            "Proporção de recortes com fissura no teste em cada superfície: "
            + ", ".join(f"{s} {pc(m['positivos'] / m['n'])}" for s, m in sorted(R["teste_por_superficie"].items())) + ".")
    add("")

    add("## 5. Limiar de confiança: qualidade contra velocidade e alarmes\n")
    add(f"O limiar foi escolhido na validação: o maior limiar que ainda mantém revocação de pelo menos {v(met['revocacao_minima_validacao'], 2)}. "
        "A ideia é que, em uma triagem, deixar passar uma fissura custa mais do que mandar uma foto a mais para revisão. "
        "Comparamos no teste três escolhas para o mesmo modelo:\n")
    linhas = []
    for rot, chave, lim in (("0,50 (padrão)", "teste_limiar_0_5", 0.5),
                            (f"{v(R['limiar_melhor_f1'], 2)} (melhor F1 na validação)", "teste_limiar_melhor_f1", R["limiar_melhor_f1"]),
                            (f"{v(R['limiar_escolhido'], 2)} (revocação mínima, o usado)", "teste_limiar_escolhido", R["limiar_escolhido"])):
        m = R[chave]
        linhas.append([rot, v(m["precisao"]), v(m["revocacao"]), v(m["f1"]), m["fp"], m["fn"]])
    add(tabela(["Limiar", "Precisão", "Revocação", "F1", "Falsos positivos", "Falsos negativos"], linhas))
    add("\nLimiar menor acusa mais fissuras e gera mais falsos positivos. Limiar maior reduz os alarmes, mas deixa passar mais fissuras. "
        "Na tela do sistema o limiar pode ser mudado em um controle, e o valor padrão é o escolhido na validação. "
        "Em relação à velocidade, o limiar não muda o tempo de cada imagem. O que pesa no tempo é a rede, a resolução da entrada "
        "e, nos vídeos, quantos recortes cada quadro tem.\n")

    add("## 6. Latência e FPS\n")
    add("Medimos o tempo de ponta a ponta de uma imagem por vez (abrir, redimensionar e rodar a rede), depois de 10 imagens de aquecimento, "
        "e também a vazão em lote.\n")
    linhas = []
    for n, r in mods.items():
        l = r["latencia"]
        linhas.append([NOMES.get(n, n), l["nome_dispositivo"], l["resolucao_entrada"], l["imagens_medidas"],
                       f"{l['ms_pre_processamento']}".replace(".", ","), f"{l['ms_rede']}".replace(".", ","),
                       f"{l['ms_por_imagem']}".replace(".", ","), f"{l['ms_p95']}".replace(".", ","),
                       f"{l['fps_uma_imagem']}".replace(".", ","), f"{l['fps_em_lote']}".replace(".", ",")])
    add(tabela(["Modelo", "Hardware", "Entrada", "Imagens", "Preparo (ms)", "Rede (ms)", "Total (ms)", "P95 (ms)",
                "FPS uma imagem", "FPS em lote"], linhas))
    lat = R["latencia"]
    add(f"\nO tempo foi medido em: {lat['nome_dispositivo']}, com {lat['threads_cpu']} thread(s) de CPU, entrada de {lat['resolucao_entrada']} pixels. "
        "Os valores mudam em outro equipamento, e uma GPU de nuvem não representa o que teria um celular ou uma caixa de campo. "
        "Para avaliar uma câmera de rua, o que importa é o FPS na máquina real, então essa medida deve ser repetida no equipamento escolhido.\n")
    cpu_arq = pasta / "latencia_cpu.json"
    if cpu_arq.exists():
        lc = json.loads(cpu_arq.read_text(encoding="utf-8"))
        add(f"Repetimos a medida do modelo escolhido na CPU do Colab ({lc['threads_cpu']} thread), que se parece mais com um equipamento simples de campo do que a GPU:\n")
        add(tabela(["Modelo", "Hardware", "Entrada", "Total (ms)", "P95 (ms)", "FPS uma imagem", "FPS em lote"],
                   [[NOMES.get(esc, esc), lc["nome_dispositivo"], lc["resolucao_entrada"], str(lc["ms_por_imagem"]).replace(".", ","),
                     str(lc["ms_p95"]).replace(".", ","), str(lc["fps_uma_imagem"]).replace(".", ","), str(lc["fps_em_lote"]).replace(".", ",")]]))
        add("\nNa GPU o tempo é muito menor. A comparação entre as duas redes só foi feita na GPU, e a ordem de velocidade pode mudar em outro equipamento.\n")
    if vid:
        add("Também processamos um vídeo curto, simulando o monitoramento urbano. Cada quadro é cortado em recortes de 256 por 256 pixels, "
            "e cada recorte passa pela rede:\n")
        add(tabela(["Quadros analisados", "Quadros positivos", "Eventos confirmados", "ms por quadro", "Quadros por segundo", "Largura de análise", "Dispositivo"],
                   [[vid["quadros_analisados"], vid["quadros_positivos"], vid["eventos_confirmados"], str(vid["ms_medio_por_quadro"]).replace(".", ","),
                     str(vid["quadros_por_segundo"]).replace(".", ","), vid["largura_alvo"], vid["dispositivo"]]]))
        add("\nUm evento só é confirmado quando o limiar é passado em 2 quadros analisados seguidos, para um quadro isolado não gerar alerta.")
        if vid.get("tipo_entrada"):
            add(f"\nEntrada usada: {vid['tipo_entrada']}.")
        if vid.get("comparacao_com_verdade"):
            c = vid["comparacao_com_verdade"]
            add(f"\nComo o mosaico foi montado por nós, sabíamos quais quadros tinham fissura. Comparando: {c['tp']} acertos em quadros com fissura, "
                f"{c['fn']} quadros com fissura não vistos, {c['fp']} alarmes falsos e {c['tn']} quadros sem fissura corretos. "
                "Isso é uma simulação com recortes do teste, não uma cena real de rua.")
        add("")
    else:
        add("O resultado do processamento de vídeo ainda não foi gerado (falta results/video_resumo.json).\n")

    add("## 7. Análise de erros\n")
    e = R["erros"]
    ex = R["erros_exportados"]
    add(f"No teste, o modelo errou {e['total']} recortes: {teste['fp']} falsos positivos (disse fissura e não havia) e {teste['fn']} falsos negativos "
        f"(havia fissura e ele não viu). Dos erros, {e['perto_do_limiar']} ficaram perto do limiar (probabilidade a menos de 0,15 do limiar), "
        f"o que indica dúvida do modelo, e {e['com_certeza']} foram com a probabilidade longe do limiar (mais de 0,35), ou seja, o modelo estava confiante e errou.\n")
    add(f"Salvamos as imagens erradas em results/erros/{esc}/falsos_positivos e falsos_negativos (até 24 de cada), com a probabilidade no nome do arquivo. "
        f"Foram {ex['falsos_positivos']} falsos positivos e {ex['falsos_negativos']} falsos negativos no total.\n")
    obs = pasta / "analise_erros.md"
    if obs.exists():
        add(obs.read_text(encoding="utf-8").strip())
        add("\nAs diferenças de desempenho entre as superfícies estão na tabela da seção 4.\n")
    else:
        add("**O que observei nas imagens erradas** (preencher depois de abrir as pastas, descrevendo só o que realmente aparece):\n")
        add("* Falsos positivos: [descrever o que aparece nas imagens]")
        add("* Falsos negativos: [descrever o que aparece nas imagens]")
        add("* Diferença entre superfícies: [comentar com base na tabela da seção 4.]\n")

    add("## 8. Funcionalidade para o CitizenTech\n")
    add("A tela do VIA VISÃO (app/triagem.py) recebe uma foto, uma sequência de fotos ou um vídeo curto. Para cada imagem ela mostra "
        "os recortes com possível fissura marcados em vermelho, a confiança do modelo, o tempo de análise e a faixa de triagem: "
        "sem indício, revisão humana ou encaminhar para inspeção. No vídeo, o sistema analisa 1 a cada N quadros, confirma o evento "
        "quando 2 quadros seguidos passam do limiar e gera um arquivo de vídeo com as marcações e um JSON com o resultado de cada quadro. "
        "A saída segue o formato de ocorrência do VIA CIDADÃO (id, categoria, confiança, limiar, triagem, localização, aviso), "
        "para o VIA ZELADORIA e o VIA CONECTA receberem como as outras ocorrências.\n")

    add("## 9. Limites\n")
    add("* A SDNET2018 tem recortes de perto, de concreto limpo e bem fotografado. Fotos ou vídeos de rua, com ângulo, distância e movimento diferentes, "
         "podem ter resultado pior, e nós não medimos isso.")
    add("* As superfícies da base não incluem asfalto de rua com buracos e remendos. O teste de vídeo mostra que o fluxo funciona, não que a precisão se mantém.")
    add("* O teste vem de fotos de origem que não aparecem no treino, mas a base inteira vem de poucos locais, então o resultado em outra cidade pode ser diferente.")
    add("* O número de fotos de origem no teste é pequeno, então as métricas por superfície variam bastante.")
    add("* O sistema aponta presença provável de fissura. Gravidade, largura, causa e risco estrutural exigem um profissional.")
    add("* O limiar e as faixas de triagem foram escolhidos nos dados da base, sem validação com equipes de inspeção.")
    notas = pasta / "notas_limites.md"
    if notas.exists():
        add(notas.read_text(encoding="utf-8").strip())
    add("")

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(L), encoding="utf-8")
    print("Relatório gerado em", destino)


if __name__ == "__main__":
    main()
