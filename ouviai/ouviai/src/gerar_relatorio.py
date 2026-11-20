"""Monta o relatório do OuviAí com os números das planilhas e as capturas de tela.

Uso:  python src/gerar_relatorio.py [pasta_do_projeto] [--pdf]
Lê dados/params.json, dados/teste_arquivos.csv, dados/ao_vivo.csv, dados/observacoes.md
e as imagens da pasta capturas/. Itens que faltam aparecem no relatório como
"(não informado)" e na lista de pendências impressa no final.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calcular_resultados import calcular  # noqa: E402

NOMES = {"campainha": "campainha", "batida_na_porta": "batida na porta", "ambiente": "ambiente", "incerto": "incerto"}
CAPTURAS = [
    ("01_data_acquisition", "Data acquisition: gravações e rótulos"),
    ("02_impulse_design", "Impulse design: Audio (MFE) e classificação"),
    ("03_generate_features", "Generate features: feature explorer"),
    ("04_classifier", "Classifier: validação do treinamento e matriz de confusão"),
    ("05_model_testing", "Model testing: Classify all nos arquivos de teste"),
    ("06_run_model_celular", "Run this model: modelo rodando ao vivo no celular"),
    ("07_ao_vivo_1", "Validação ao vivo, captura 1"),
    ("08_ao_vivo_2", "Validação ao vivo, captura 2"),
]


def pc(x):
    return "n/d" if x is None else f"{x * 100:.0f}%".replace(".", ",")


def val(x, pend, nome):
    if x is None or x == "":
        pend.append(nome)
        return "(não informado)"
    return str(x).replace(".", ",") if isinstance(x, float) else str(x)


def tabela(cab, linhas):
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join(["---"] * len(cab)) + "|"]
    out += ["| " + " | ".join(str(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)


def tab_matriz(m, classes):
    prev = list(next(iter(m.values())).keys())
    cab = ["Real \\ Previsto"] + [NOMES[c] for c in prev] + ["Total"]
    return tabela(cab, [[NOMES[r]] + [m[r][p] for p in prev] + [sum(m[r].values())] for r in classes])


def tab_classe(met, classes):
    return tabela(["Classe", "Arquivos", "Acertos", "Revocação", "Precisão"],
                  [[NOMES[c], met["por_classe"][c]["n"], met["por_classe"][c]["acertos"],
                    pc(met["por_classe"][c]["revocacao"]), pc(met["por_classe"][c]["precisao"])] for c in classes])


def imagem(raiz, base, legenda, pend):
    for ext in ("png", "jpg", "jpeg"):
        p = raiz / "capturas" / f"{base}.{ext}"
        if p.exists():
            larg = "{width=35%}" if base.startswith("06") else ""
            return f"![{legenda}]({p.resolve()}){larg}\n\n*Figura: {legenda}.*\n"
    if not base.startswith(("07", "08")):
        pend.append(f"captura {base}")
    return f"(captura ausente: {legenda})\n"


def galeria(raiz, P, A):
    itens = P.get("capturas_ao_vivo") or []
    prev = {int(l["tentativa"]): l for l in A.get("linhas", [])}
    cel = []
    for it in itens:
        arq = None
        for ext in ("png", "jpg", "jpeg"):
            c = raiz / "capturas" / f"{it['arquivo']}.{ext}"
            if c.exists():
                arq = c
                break
        if not arq:
            continue
        l = prev.get(it["tentativa"], {})
        real = NOMES.get((l.get("classe_real") or "").strip(), "?")
        pr = NOMES.get((l.get("classe_prevista") or "").strip(), "?")
        cel.append(f'<td style="text-align:center;vertical-align:top;padding:4px"><img src="{arq.resolve()}" width="140"><br><small>Tentativa {it["tentativa"]}<br>real: {real}<br>previsto: {pr}</small></td>')
    if not cel:
        return "(capturas das tentativas ausentes)\n"
    linhas = ["<tr>" + "".join(cel[i:i + 5]) + "</tr>" for i in range(0, len(cel), 5)]
    return "<table>" + "".join(linhas) + "</table>\n"


def secao_obs(texto, titulo):
    m = re.search(rf"## {re.escape(titulo)}\n(.*?)(?=\n## |\Z)", texto, flags=re.S)
    corpo = m.group(1).strip() if m else ""
    return corpo


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    raiz = Path(args[0]) if args else Path(".")
    P = json.loads((raiz / "dados" / "params.json").read_text(encoding="utf-8"))
    classes = P["classes"]
    R = calcular(raiz / "dados", classes)
    obs = (raiz / "dados" / "observacoes.md").read_text(encoding="utf-8") if (raiz / "dados" / "observacoes.md").exists() else ""
    pend = []
    L = []
    add = L.append

    add("# OuviAí: assistente sonoro para acessibilidade\n")
    add("**Módulo do VIA CIDADÃO, Global Solution 2026.2, desafio CitizenTech**\n")
    add("Disciplina: Physical Computing, Embedded AI, Robotics & Cognitive IoT\n")
    add("Integrantes (nome completo e RM):\n")
    for i in P["integrantes"]:
        add(f"* {i['nome']}, RM {i['rm']}")
    add("")

    add("## 1. Problema, público e ODS\n")
    add("Uma pessoa com deficiência auditiva pode não perceber sons que avisam que alguém chegou, como a campainha ou uma batida na porta. "
        "Isso atrapalha o recebimento de uma visita, de uma entrega ou de um aviso de vizinho, e em alguns casos a pessoa precisa depender de alguém por perto ou ficar olhando para a porta. "
        "O OuviAí é um protótipo educacional que usa o microfone do celular para reconhecer três situações: campainha, batida na porta e ambiente (nenhum desses eventos), e mostra a resposta de forma visual na tela.\n")
    add("O público beneficiado são pessoas surdas ou com perda auditiva que moram sozinhas ou ficam sozinhas em casa em parte do dia, e também pessoas que usam fones de ouvido ou estão em ambientes barulhentos. "
        "No VIA CIDADÃO, o OuviAí é a entrada de som do módulo VIA ALERTA: ele transforma um som do cotidiano em um aviso visual, no mesmo espírito do projeto, que usa tecnologia para incluir quem hoje fica de fora.\n")
    add("Objetivos de Desenvolvimento Sustentável relacionados: **ODS 10, Redução das desigualdades**, porque reduz uma barreira de comunicação enfrentada por pessoas com deficiência, e **ODS 11, Cidades e comunidades sustentáveis**, porque contribui para moradias e espaços urbanos mais acessíveis e inclusivos.\n")

    add("## 2. Arquitetura e dados\n")
    add("O fluxo do protótipo é:\n")
    add("```\nSom do ambiente  ->  Microfone do celular  ->  Modelo de IA (MFE + CNN)  ->  Classificação e resposta visual no celular\n```\n")
    add("O modelo roda no navegador do celular pelo recurso Run this model do Edge Impulse. O áudio é processado no próprio aparelho, sem aplicativo próprio.\n")
    g = P["gravacoes"]
    add(f"Todas as gravações têm {P['duracao_amostra_s']} segundos, taxa de amostragem de {P['taxa_amostragem_hz'] // 1000} kHz e áudio {P['canais']}. Distribuição dos dados:\n")
    add(tabela(["Classe", "Training", "Test"], [[NOMES[c], g[c]["treino"], g[c]["teste"]] for c in classes]))
    add("")
    add("Origem dos áudios: " + val(P.get("origem_audios"), pend, "origem dos áudios (params.json)") + "\n")
    add("Celular e navegador usados: " + val(P.get("celular_e_navegador"), pend, "celular e navegador (params.json)") + "\n")
    add("As gravações de Test foram feitas em outro momento e não entraram no Training. Os rótulos usados foram exatamente: " + ", ".join(classes) + ".\n")

    add("## 3. Coleta e tratamento dos dados\n")
    add("Usamos o Edge Impulse conectado ao celular para gravar. Para cada classe, gravamos 20 áudios de 5 segundos, sendo 15 para Training e 5 independentes para Test. "
        "Depois de gravar, ouvimos os áudios e conferimos se cada um continha o evento do seu rótulo. Na classe ambiente, evitamos conversas que identifiquem pessoas.\n")
    add(imagem(raiz, "01_data_acquisition", "Data acquisition: gravações e rótulos", pend))

    add("## 4. Modelo de IA: MFE e CNN\n")
    I, M, N = P["impulse"], P["mfe"], P["rede_neural"]
    add("O áudio bruto passa por um bloco de processamento Audio (MFE), que transforma o som em um espectrograma com energia por faixa de frequência na escala Mel, e depois por uma rede neural convolucional (CNN) que classifica entre as três classes.\n")
    add(tabela(["Parâmetro", "Valor"], [
        ["Janela (window size)", val(I["window_size_ms"], pend, "window size") + " ms"],
        ["Passo da janela (window increase)", val(I["window_increase_ms"], pend, "window increase") + " ms"],
        ["MFE: frame length", val(M["frame_length_s"], pend, "MFE frame length") + " s"],
        ["MFE: frame stride", val(M["frame_stride_s"], pend, "MFE frame stride") + " s"],
        ["MFE: filter number", val(M["filter_number"], pend, "MFE filter number")],
        ["MFE: FFT length", val(M["fft_length"], pend, "MFE fft length")],
        ["MFE: low frequency", val(M["low_frequency_hz"], pend, "MFE low frequency") + " Hz"],
        ["MFE: high frequency", val(M["high_frequency_hz"], pend, "MFE high frequency") + ("" if isinstance(M["high_frequency_hz"], str) else " Hz")],
        ["MFE: noise floor", val(M["noise_floor_db"], pend, "MFE noise floor") + " dB"],
        ["Arquitetura da rede", val(N["arquitetura"], pend, "arquitetura da rede")],
        ["Épocas", val(N["epocas"], pend, "épocas")],
        ["Taxa de aprendizado", val(N["taxa_de_aprendizado"], pend, "taxa de aprendizado")],
        ["Parte do Training usada na validação", val(N["validacao_percentual"], pend, "tamanho do conjunto de validação (Configurações de treinamento avançadas)") + "%"],
    ]))
    add("")
    add(imagem(raiz, "02_impulse_design", "Impulse design: Audio (MFE) e classificação", pend))
    add(imagem(raiz, "03_generate_features", "Generate features: feature explorer", pend))

    add("## 5. Resultados\n")
    add("São três avaliações diferentes, e elas não devem ser misturadas: a validação do treinamento, o teste com arquivos inéditos e a validação ao vivo no celular.\n")

    add("### 5.1 Validação do treinamento\n")
    VT = P["validacao_treino"]
    add(f"Durante o treinamento, o Edge Impulse separa {N['validacao_percentual']}% do Training para validação. "
        f"Acurácia de validação informada: {val(VT['acuracia_percentual'], pend, 'acurácia de validação')}%, perda: {val(VT['perda'], pend, 'perda de validação')}. "
        "Esse valor mostra como o modelo se saiu em dados parecidos com os do treino, e por isso costuma ser mais otimista que o teste.\n")
    add(imagem(raiz, "04_classifier", "Classifier: validação do treinamento e matriz de confusão", pend))

    add("### 5.2 Teste com arquivos inéditos (Model testing, Classify all)\n")
    T = R["teste"]
    if T.get("metricas"):
        mt = T["metricas"]
        add(f"O teste usou {T['linhas_preenchidas']} arquivos que não foram usados no Training (5 por classe). "
            f"O modelo acertou {mt['acertos']} de {mt['total']}, o que dá {pc(mt['acuracia'])} de acurácia. "
            "Com só 5 arquivos por classe, cada erro muda a revocação da classe em 20 pontos percentuais, então o resultado tem muita margem de variação.\n")
        add(tabela(["Arquivo", "Classe real", "Classe prevista (mais frequente)", "Resultado por janela", "Acertou?"],
                   [[l["arquivo"], NOMES[l["classe_real"].strip()], NOMES[l["classe_prevista"].strip()], (l.get("confianca_exibida") or "").strip() or "n/d",
                     "sim" if l["classe_real"].strip() == l["classe_prevista"].strip() else "não"] for l in T["linhas"]]))
        if T.get("incertos"):
            add(f"\nEm {T['incertos']} dos {mt['total']} arquivos o resultado foi \"incerto\": nenhuma classe passou do limiar de confiança do Edge Impulse (60%). A resposta \"incerto\" conta como erro, porque o modelo não decidiu.\n")
        add("\nMatriz de confusão do teste:\n")
        add(tab_matriz(T["matriz"], classes))
        add("\nResultado por classe:\n")
        add(tab_classe(mt, classes))
        add("")
    else:
        pend.append("planilha teste_arquivos.csv sem classe_prevista")
        add("(planilha do teste ainda não preenchida)\n")
    add(imagem(raiz, "05_model_testing", "Model testing: Classify all nos arquivos de teste", pend))
    corpo = secao_obs(obs, "Erros no teste com arquivos")
    if not corpo or corpo.startswith("Descreva"):
        pend.append("discussão dos erros do teste (observacoes.md)")
        corpo = "(discussão dos erros não preenchida)"
    add("**Discussão dos erros.** " + corpo + "\n")

    add("### 5.3 Validação ao vivo no celular\n")
    A = R["ao_vivo"]
    if A.get("metricas"):
        ma = A["metricas"]
        add(f"Com o modelo aberto no navegador do celular (Run this model), fizemos {A['linhas_preenchidas']} tentativas, anotando o som produzido, a classe prevista e o acerto ou erro. "
            f"Acertamos {ma['acertos']} de {ma['total']}, ou seja, **{pc(ma['acuracia'])} de acerto**.\n")
        add(tabela(["Tentativa", "Som produzido", "Classe real", "Classe prevista", "Confiança exibida", "Acertou?", "Observação"],
                   [[l["tentativa"], (l.get("som_produzido") or "").strip() or "n/d", NOMES[l["classe_real"].strip()], NOMES[l["classe_prevista"].strip()],
                     (l.get("confianca_exibida") or "").strip() or "n/d",
                     "sim" if l["classe_real"].strip() == l["classe_prevista"].strip() else "não", (l.get("observacao") or "").strip()] for l in A["linhas"]]))
        add("\nMatriz de confusão ao vivo:\n")
        add(tab_matriz(A["matriz"], classes))
        add("\nResultado por classe:\n")
        add(tab_classe(ma, classes))
        if "alarmes_falsos" in A:
            add(f"\nFalsos positivos na classe ambiente: em {A['ambiente_n']} tentativas de ambiente, o modelo indicou campainha ou batida em {A['alarmes_falsos']}. "
                f"Eventos perdidos: em {A['eventos_n']} tentativas com campainha ou batida, o modelo respondeu ambiente em {A['eventos_perdidos']}.\n")
        add("A probabilidade mostrada na tela do celular não é a acurácia: ela é a confiança do modelo naquele instante. A acurácia só aparece quando se compara a resposta do modelo com o som que de fato foi produzido, como nesta tabela.\n")
    else:
        pend.append("planilha ao_vivo.csv sem classe_prevista")
        add("(planilha das 15 tentativas ainda não preenchida)\n")
    add(imagem(raiz, "06_run_model_celular", "Run this model: modelo rodando ao vivo no celular", pend))
    add("Capturas da tela do celular em cada tentativa. A classe prevista é a que aparece no topo da tela.\n")
    add(galeria(raiz, P, A))
    corpo = secao_obs(obs, "Erros na validação ao vivo")
    if not corpo or corpo.startswith("Descreva"):
        pend.append("discussão dos erros ao vivo (observacoes.md)")
        corpo = "(discussão não preenchida)"
    add("**Discussão.** " + corpo + "\n")

    add("### 5.4 Como ler as três avaliações\n")
    add("A validação do treinamento usa uma parte dos próprios dados de treino. O teste com arquivos usa gravações inéditas, mas feitas por nós, em condições parecidas. "
        "A validação ao vivo é a mais próxima do uso real, porque o som passa pelo microfone do celular em tempo real, com ruído e distância. "
        "Por isso é esperado que os números caiam da primeira para a última, e é a validação ao vivo que mais diz sobre o benefício concreto para o cidadão.\n")

    add("## 6. Integração com o VIA CIDADÃO e evolução\n")
    add("O OuviAí é a entrada de som do módulo VIA ALERTA. O protótipo entregue mostra a resposta visual no navegador do celular, sem aplicativo próprio. "
        "Como proposta de evolução, que não foi implementada nesta entrega: (1) enviar uma notificação no celular quando o modelo reconhecer campainha ou batida; "
        "(2) acionar a vibração do aparelho com um padrão diferente para cada evento; (3) piscar a tela ou uma luz externa; "
        "(4) enviar o aviso para um relógio inteligente; (5) usar um ESP32 com microfone e uma tira de LED fixados perto da porta, como parte do VIA ALERTA. "
        "Cada evento reconhecido poderia virar uma ocorrência no mesmo formato JSON dos outros módulos (módulo, categoria, confiança, data e hora), para o VIA CONECTA registrar e consultar o histórico.\n")

    add("## 7. Privacidade, segurança e limitações\n")
    add("* Não gravamos conversas identificáveis. Os áudios de ambiente foram de ruídos do dia a dia, e quem estava no local concordou com as gravações.")
    add("* O modelo roda no navegador do celular, e a classificação ao vivo não precisa guardar o áudio. Os áudios de treino e teste devem ser apagados do projeto depois da avaliação, se não forem mais necessários.")
    add("* O protótipo é educacional. Ele não substitui sistemas de segurança, alarmes ou alertas de emergência, e não deve ser usado como única forma de saber que alguém chegou.")
    add("* O conjunto de dados é pequeno (15 gravações de treino por classe) e foi gravado em poucos lugares e com poucos aparelhos. Outras campainhas, outras portas e outros ruídos podem ter resultado pior.")
    add("* Com 5 arquivos de teste por classe e 5 tentativas ao vivo por classe, os percentuais variam muito. Um erro a mais ou a menos muda o resultado de forma grande.")
    add("* Sons parecidos, como uma campainha tocando na televisão ou uma batida de outro lugar, podem gerar falsos positivos.\n")

    add("## 8. Conclusão\n")
    if T.get("metricas") and A.get("metricas"):
        add(f"No teste com arquivos inéditos o modelo teve {pc(T['metricas']['acuracia'])} de acurácia, e na validação ao vivo no celular teve {pc(A['metricas']['acuracia'])}. "
            "Esses números mostram que o fluxo funciona de ponta a ponta no celular, mas, pelo tamanho pequeno dos testes, não dizem se o modelo seria confiável no uso diário. "
            "Os próximos passos são gravar mais exemplos em mais lugares, testar com mais tentativas e implementar a notificação e a vibração.\n")
    else:
        add("(conclusão será escrita quando as planilhas estiverem preenchidas)\n")

    texto = "\n".join(L)
    saida = raiz / "docs" / "relatorio_ouviai.md"
    saida.parent.mkdir(exist_ok=True)
    saida.write_text(texto, encoding="utf-8")
    print("Relatório gerado em", saida)
    if pend:
        print("\nPendências:")
        for p in dict.fromkeys(pend):
            print(" -", p)
    if "--pdf" in sys.argv:
        css = raiz / "docs" / "estilo_pdf.css"
        html = Path("/tmp/relatorio_ouviai.html")
        subprocess.run(["pandoc", str(saida), "-f", "markdown+lists_without_preceding_blankline+hard_line_breaks", "-t", "html5", "-s",
                        "--metadata", "title=OuviAí", "--css", str(css), "--embed-resources", "-o", str(html)], check=True)
        h = re.sub(r'<header id="title-block-header">.*?</header>', "", html.read_text(encoding="utf-8"), flags=re.S)
        html.write_text(h, encoding="utf-8")
        subprocess.run(["wkhtmltopdf", "--quiet", "--disable-smart-shrinking", "--enable-local-file-access", "-s", "A4", "-T", "16mm", "-B", "16mm",
                        "-L", "15mm", "-R", "15mm", str(html), str(raiz / "docs" / "relatorio_ouviai.pdf")], check=False)
        print("PDF em", raiz / "docs" / "relatorio_ouviai.pdf")


if __name__ == "__main__":
    main()
