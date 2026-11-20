# OuviAí: assistente sonoro para acessibilidade

**Módulo do VIA CIDADÃO, Global Solution 2026.2, desafio CitizenTech**

Disciplina: Physical Computing, Embedded AI, Robotics & Cognitive IoT

Integrantes (nome completo e RM):

* Mayara Mota, RM 563887
* Gabriel Palmeira, RM 563522

## 1. Problema, público e ODS

Uma pessoa com deficiência auditiva pode não perceber sons que avisam que alguém chegou, como a campainha ou uma batida na porta. Isso atrapalha o recebimento de uma visita, de uma entrega ou de um aviso de vizinho, e em alguns casos a pessoa precisa depender de alguém por perto ou ficar olhando para a porta. O OuviAí é um protótipo educacional que usa o microfone do celular para reconhecer três situações: campainha, batida na porta e ambiente (nenhum desses eventos), e mostra a resposta de forma visual na tela.

O público beneficiado são pessoas surdas ou com perda auditiva que moram sozinhas ou ficam sozinhas em casa em parte do dia, e também pessoas que usam fones de ouvido ou estão em ambientes barulhentos. No VIA CIDADÃO, o OuviAí é a entrada de som do módulo VIA ALERTA: ele transforma um som do cotidiano em um aviso visual, no mesmo espírito do projeto, que usa tecnologia para incluir quem hoje fica de fora.

Objetivos de Desenvolvimento Sustentável relacionados: **ODS 10, Redução das desigualdades**, porque reduz uma barreira de comunicação enfrentada por pessoas com deficiência, e **ODS 11, Cidades e comunidades sustentáveis**, porque contribui para moradias e espaços urbanos mais acessíveis e inclusivos.

## 2. Arquitetura e dados

O fluxo do protótipo é:

```
Som do ambiente  ->  Microfone do celular  ->  Modelo de IA (MFE + CNN)  ->  Classificação e resposta visual no celular
```

O modelo roda no navegador do celular pelo recurso Run this model do Edge Impulse. O áudio é processado no próprio aparelho, sem aplicativo próprio.

Todas as gravações têm 5 segundos, taxa de amostragem de 16 kHz e áudio mono. Distribuição dos dados:

| Classe | Training | Test |
|---|---|---|
| campainha | 15 | 5 |
| batida na porta | 15 | 5 |
| ambiente | 15 | 5 |

Origem dos áudios: Os sons de treino, de teste e da demonstração ao vivo foram gravados com o microfone do celular, a partir de vídeos do YouTube.

Celular e navegador usados: celular Samsung, com o navegador do próprio celular, que nas capturas aparece como o Samsung Internet

As gravações de Test foram feitas em outro momento e não entraram no Training. Os rótulos usados foram exatamente: campainha, batida_na_porta, ambiente.

## 3. Coleta e tratamento dos dados

Usamos o Edge Impulse conectado ao celular para gravar. Para cada classe, gravamos 20 áudios de 5 segundos, sendo 15 para Training e 5 independentes para Test. Depois de gravar, ouvimos os áudios e conferimos se cada um continha o evento do seu rótulo. Na classe ambiente, evitamos conversas que identifiquem pessoas.

![Data acquisition: gravações e rótulos](/home/claude/ouviai/capturas/01_data_acquisition.png)

*Figura: Data acquisition: gravações e rótulos.*

## 4. Modelo de IA: MFE e CNN

O áudio bruto passa por um bloco de processamento Audio (MFE), que transforma o som em um espectrograma com energia por faixa de frequência na escala Mel, e depois por uma rede neural convolucional (CNN) que classifica entre as três classes.

| Parâmetro | Valor |
|---|---|
| Janela (window size) | 1000 ms |
| Passo da janela (window increase) | 500 ms |
| MFE: frame length | 0,02 s |
| MFE: frame stride | 0,01 s |
| MFE: filter number | 40 |
| MFE: FFT length | 256 |
| MFE: low frequency | 0 Hz |
| MFE: high frequency | não definido na tela |
| MFE: noise floor | -52 dB |
| Arquitetura da rede | entrada de 3.960 características, redimensionar (40 colunas), convolução e pooling 1D (8 filtros, kernel 3), abandono 0,25, convolução e pooling 1D (16 filtros, kernel 3), abandono 0,25, achatar, saída com 3 classes |
| Épocas | 100 |
| Taxa de aprendizado | 0,005 |
| Parte do Training usada na validação | 20% |

![Impulse design: Audio (MFE) e classificação](/home/claude/ouviai/capturas/02_impulse_design.png)

*Figura: Impulse design: Audio (MFE) e classificação.*

![Generate features: feature explorer](/home/claude/ouviai/capturas/03_generate_features.png)

*Figura: Generate features: feature explorer.*

## 5. Resultados

São três avaliações diferentes, e elas não devem ser misturadas: a validação do treinamento, o teste com arquivos inéditos e a validação ao vivo no celular.

### 5.1 Validação do treinamento

Durante o treinamento, o Edge Impulse separa 20% do Training para validação. Acurácia de validação informada: 54,3%, perda: 0,88. Esse valor mostra como o modelo se saiu em dados parecidos com os do treino, e por isso costuma ser mais otimista que o teste.

![Classifier: validação do treinamento e matriz de confusão](/home/claude/ouviai/capturas/04_classifier.png)

*Figura: Classifier: validação do treinamento e matriz de confusão.*

### 5.2 Teste com arquivos inéditos (Model testing, Classify all)

O teste usou 15 arquivos que não foram usados no Training (5 por classe). O modelo acertou 1 de 15, o que dá 7% de acurácia. Com só 5 arquivos por classe, cada erro muda a revocação da classe em 20 pontos percentuais, então o resultado tem muita margem de variação.

| Arquivo | Classe real | Classe prevista (mais frequente) | Resultado por janela | Acertou? |
|---|---|---|---|---|
| ambiente_teste_1 | ambiente | incerto | 9 incerto | não |
| ambiente_teste_2 | ambiente | incerto | 7 incerto, 2 batida_na_porta | não |
| ambiente_teste_3 | ambiente | incerto | 6 incerto, 2 campainha, 1 ambiente | não |
| ambiente_teste_4 | ambiente | batida na porta | 5 batida_na_porta, 4 incerto | não |
| ambiente_teste_5 | ambiente | incerto | 4 incerto, 3 batida_na_porta, 1 outra | não |
| batida_teste_1 | batida na porta | incerto | 8 incerto, 1 batida_na_porta | não |
| batida_teste_2 | batida na porta | incerto | 5 incerto, 4 batida_na_porta | não |
| batida_teste_3 | batida na porta | incerto | 6 incerto, 3 batida_na_porta | não |
| batida_teste_4 | batida na porta | incerto | 7 incerto, 2 batida_na_porta | não |
| batida_teste_5 | batida na porta | incerto | 9 incerto | não |
| campainha_teste_1 | campainha | incerto | 9 incerto | não |
| campainha_teste_2 | campainha | incerto | 6 incerto, 3 ambiente | não |
| campainha_teste_3 | campainha | incerto | 6 incerto, 3 ambiente | não |
| campainha_teste_4 | campainha | incerto | 8 incerto, 1 outra | não |
| campainha_teste_5 | campainha | campainha | 1 campainha (áudio de 1 s, 1 janela) | sim |

Em 13 dos 15 arquivos o resultado foi "incerto": nenhuma classe passou do limiar de confiança do Edge Impulse (60%). A resposta "incerto" conta como erro, porque o modelo não decidiu.


Matriz de confusão do teste:

| Real \ Previsto | campainha | batida na porta | ambiente | incerto | Total |
|---|---|---|---|---|---|
| campainha | 1 | 0 | 0 | 4 | 5 |
| batida na porta | 0 | 0 | 0 | 5 | 5 |
| ambiente | 0 | 1 | 0 | 4 | 5 |

Resultado por classe:

| Classe | Arquivos | Acertos | Revocação | Precisão |
|---|---|---|---|---|
| campainha | 5 | 1 | 20% | 100% |
| batida na porta | 5 | 0 | 0% | 0% |
| ambiente | 5 | 0 | 0% | n/d |

![Model testing: Classify all nos arquivos de teste](/home/claude/ouviai/capturas/05_model_testing.png)

*Figura: Model testing: Classify all nos arquivos de teste.*

**Discussão dos erros.** No teste com os 15 arquivos que não foram usados no treino, o modelo acertou 1 de 15. Em 13 arquivos o resultado mais frequente foi "incerto", ou seja, nenhuma classe passou de 60% de confiança nas janelas de 1 segundo. Em 1 arquivo de ambiente, a classe mais frequente foi batida na porta. O único acerto foi um áudio de campainha com apenas 1 segundo, que tem uma só janela e por isso é uma evidência fraca, além de ser mais curto que os 5 segundos pedidos.

Nos arquivos de batida na porta, entre 0 e 4 das 9 janelas foram classificadas como batida, e o restante ficou como incerto. Ou seja, o modelo reconheceu alguns trechos, mas não de forma firme.

Possíveis causas, que não chegamos a testar: cada janela de 1 segundo recebe o rótulo do arquivo inteiro, então janelas de silêncio dentro de um áudio de campainha ou de batida ficam parecidas com ambiente; o conjunto de treino é pequeno, com 15 áudios por classe; e os áudios de teste foram gravados em outro momento, com condições um pouco diferentes. A acurácia de validação do treino foi de 54,3%, bem acima da do teste, o que mostra que o modelo não generalizou bem. Decidimos entregar o modelo desta primeira rodada de treino, sem ajustes depois de ver o teste, para não usar os dados de teste no ajuste.

### 5.3 Validação ao vivo no celular

Com o modelo aberto no navegador do celular (Run this model), fizemos 15 tentativas, anotando o som produzido, a classe prevista e o acerto ou erro. Acertamos 12 de 15, ou seja, **80% de acerto**.

| Tentativa | Som produzido | Classe real | Classe prevista | Confiança exibida | Acertou? | Observação |
|---|---|---|---|---|---|---|
| 1 | som de vídeo do YouTube | campainha | campainha | 1.00 | sim |  |
| 2 | som de vídeo do YouTube | campainha | campainha | 1.00 | sim |  |
| 3 | som de vídeo do YouTube | campainha | campainha | 1.00 | sim |  |
| 4 | som de vídeo do YouTube | campainha | campainha | 0.92 | sim |  |
| 5 | som de vídeo do YouTube | campainha | campainha | 0.96 | sim |  |
| 6 | som de vídeo do YouTube | batida na porta | batida na porta | 0.98 | sim |  |
| 7 | som de vídeo do YouTube | batida na porta | batida na porta | 0.85 | sim |  |
| 8 | som de vídeo do YouTube | batida na porta | incerto | No event detected | não | Maior janela de batida 0.44, abaixo do limiar de 0.60 |
| 9 | som de vídeo do YouTube | batida na porta | ambiente | 0.63 | não | Janelas anteriores mostravam batida 0.85 e 0.88, mas a classe final foi ambiente |
| 10 | som de vídeo do YouTube | batida na porta | incerto | No event detected | não | Janelas anteriores mostravam batida 0.80 e 0.92, mas a classe final foi No event detected |
| 11 | som de vídeo do YouTube | ambiente | ambiente | 1.00 | sim |  |
| 12 | som de vídeo do YouTube | ambiente | ambiente | 0.79 | sim | Janelas anteriores com campainha 0.67 e 0.94 |
| 13 | som de vídeo do YouTube | ambiente | ambiente | 0.98 | sim |  |
| 14 | som de vídeo do YouTube | ambiente | ambiente | 0.88 | sim |  |
| 15 | som de vídeo do YouTube | ambiente | ambiente | 0.93 | sim | Janelas anteriores com batida 0.78 a 0.96 |

Matriz de confusão ao vivo:

| Real \ Previsto | campainha | batida na porta | ambiente | incerto | Total |
|---|---|---|---|---|---|
| campainha | 5 | 0 | 0 | 0 | 5 |
| batida na porta | 0 | 2 | 1 | 2 | 5 |
| ambiente | 0 | 0 | 5 | 0 | 5 |

Resultado por classe:

| Classe | Arquivos | Acertos | Revocação | Precisão |
|---|---|---|---|---|
| campainha | 5 | 5 | 100% | 100% |
| batida na porta | 5 | 2 | 40% | 100% |
| ambiente | 5 | 5 | 100% | 83% |

Falsos positivos na classe ambiente: em 5 tentativas de ambiente, o modelo indicou campainha ou batida em 0. Eventos perdidos: em 10 tentativas com campainha ou batida, o modelo respondeu ambiente em 1.

A probabilidade mostrada na tela do celular não é a acurácia: ela é a confiança do modelo naquele instante. A acurácia só aparece quando se compara a resposta do modelo com o som que de fato foi produzido, como nesta tabela.

![Run this model: modelo rodando ao vivo no celular](/home/claude/ouviai/capturas/06_run_model_celular.jpg){width=35%}

*Figura: Run this model: modelo rodando ao vivo no celular.*

Capturas da tela do celular em cada tentativa. A classe prevista é a que aparece no topo da tela.

<table><tr><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/06_run_model_celular.jpg" width="140"><br><small>Tentativa 1<br>real: campainha<br>previsto: campainha</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/10_ao_vivo_2132_campainha_a.jpg" width="140"><br><small>Tentativa 2<br>real: campainha<br>previsto: campainha</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/11_ao_vivo_2132_campainha_b.jpg" width="140"><br><small>Tentativa 3<br>real: campainha<br>previsto: campainha</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/12_ao_vivo_2132_campainha_c.jpg" width="140"><br><small>Tentativa 4<br>real: campainha<br>previsto: campainha</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/13_ao_vivo_2133_campainha_d.jpg" width="140"><br><small>Tentativa 5<br>real: campainha<br>previsto: campainha</small></td></tr><tr><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/07_ao_vivo_1.jpg" width="140"><br><small>Tentativa 6<br>real: batida na porta<br>previsto: batida na porta</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/09_ao_vivo_2131_batida.jpg" width="140"><br><small>Tentativa 7<br>real: batida na porta<br>previsto: batida na porta</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/18_ao_vivo_2144_batida_a.jpg" width="140"><br><small>Tentativa 8<br>real: batida na porta<br>previsto: incerto</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/19_ao_vivo_2144_batida_b.jpg" width="140"><br><small>Tentativa 9<br>real: batida na porta<br>previsto: ambiente</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/20_ao_vivo_2144_batida_c.jpg" width="140"><br><small>Tentativa 10<br>real: batida na porta<br>previsto: incerto</small></td></tr><tr><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/08_ao_vivo_2.jpg" width="140"><br><small>Tentativa 11<br>real: ambiente<br>previsto: ambiente</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/14_ao_vivo_2136_ambiente_a.jpg" width="140"><br><small>Tentativa 12<br>real: ambiente<br>previsto: ambiente</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/15_ao_vivo_2138_ambiente_b.jpg" width="140"><br><small>Tentativa 13<br>real: ambiente<br>previsto: ambiente</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/16_ao_vivo_2139_ambiente_c.jpg" width="140"><br><small>Tentativa 14<br>real: ambiente<br>previsto: ambiente</small></td><td style="text-align:center;vertical-align:top;padding:4px"><img src="/home/claude/ouviai/capturas/17_ao_vivo_2139_ambiente_d.jpg" width="140"><br><small>Tentativa 15<br>real: ambiente<br>previsto: ambiente</small></td></tr></table>

**Discussão.** Ao vivo no celular, o modelo acertou 12 de 15 tentativas, ou 80%. Os 3 erros foram todos na classe batida na porta: 2 tentativas ficaram como "No event detected" e 1 ficou como ambiente. Campainha e ambiente acertaram 5 de 5, e nenhuma das 5 tentativas de ambiente foi classificada como evento, então não houve falso positivo nessa classe.

Nas tentativas 9 e 10, as linhas da tabela do celular mostram janelas de batida com confiança de 0,80 a 0,92 pouco antes da resposta final, ou seja, o modelo chegou a reconhecer a batida, mas a classe exibida no fim mudou. Na tentativa 8, a maior confiança de batida foi 0,44, abaixo do limiar de 0,60.

O resultado ao vivo foi melhor que o do teste com arquivos, e não sabemos a causa com certeza. Uma explicação possível é a diferença no jeito de medir: o teste confere cada janela com o limiar de 60%, e ao vivo lemos a classe mostrada no topo da tela, sem exigir que todas as janelas acertem. Não testamos essa explicação. Como foram só 5 tentativas por classe, um erro a mais ou a menos muda o resultado da classe em 20 pontos percentuais.

### 5.4 Como ler as três avaliações

A validação do treinamento usa uma parte dos próprios dados de treino. O teste com arquivos usa gravações inéditas, mas feitas por nós, em condições parecidas. A validação ao vivo é a mais próxima do uso real, porque o som passa pelo microfone do celular em tempo real, com ruído e distância. Por isso é esperado que os números caiam da primeira para a última, e é a validação ao vivo que mais diz sobre o benefício concreto para o cidadão.

## 6. Integração com o VIA CIDADÃO e evolução

O OuviAí é a entrada de som do módulo VIA ALERTA. O protótipo entregue mostra a resposta visual no navegador do celular, sem aplicativo próprio. Como proposta de evolução, que não foi implementada nesta entrega: (1) enviar uma notificação no celular quando o modelo reconhecer campainha ou batida; (2) acionar a vibração do aparelho com um padrão diferente para cada evento; (3) piscar a tela ou uma luz externa; (4) enviar o aviso para um relógio inteligente; (5) usar um ESP32 com microfone e uma tira de LED fixados perto da porta, como parte do VIA ALERTA. Cada evento reconhecido poderia virar uma ocorrência no mesmo formato JSON dos outros módulos (módulo, categoria, confiança, data e hora), para o VIA CONECTA registrar e consultar o histórico.

## 7. Privacidade, segurança e limitações

* Não gravamos conversas identificáveis. Os áudios de ambiente foram de ruídos do dia a dia, e quem estava no local concordou com as gravações.
* O modelo roda no navegador do celular, e a classificação ao vivo não precisa guardar o áudio. Os áudios de treino e teste devem ser apagados do projeto depois da avaliação, se não forem mais necessários.
* O protótipo é educacional. Ele não substitui sistemas de segurança, alarmes ou alertas de emergência, e não deve ser usado como única forma de saber que alguém chegou.
* O conjunto de dados é pequeno (15 gravações de treino por classe) e foi gravado em poucos lugares e com poucos aparelhos. Outras campainhas, outras portas e outros ruídos podem ter resultado pior.
* Com 5 arquivos de teste por classe e 5 tentativas ao vivo por classe, os percentuais variam muito. Um erro a mais ou a menos muda o resultado de forma grande.
* Sons parecidos, como uma campainha tocando na televisão ou uma batida de outro lugar, podem gerar falsos positivos.

## 8. Conclusão

No teste com arquivos inéditos o modelo teve 7% de acurácia, e na validação ao vivo no celular teve 80%. Esses números mostram que o fluxo funciona de ponta a ponta no celular, mas, pelo tamanho pequeno dos testes, não dizem se o modelo seria confiável no uso diário. Os próximos passos são gravar mais exemplos em mais lugares, testar com mais tentativas e implementar a notificação e a vibração.
