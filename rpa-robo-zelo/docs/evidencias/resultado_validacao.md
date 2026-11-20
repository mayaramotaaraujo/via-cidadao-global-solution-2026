# Resultado da validação (gerado por `python -m scripts.validar`)

## Parte A: qualidade da IA no conjunto de TESTE (resultado oficial)

Conjunto escrito depois que as regras e o modelo foram finalizados. Nada foi ajustado olhando para ele.

- Amostra: **64 relatos** escritos à mão, 8 por categoria, com categoria e urgência esperadas (`dados/teste/casos_teste_rotulados.csv`).
- Base de treino: 880 relatos sintéticos gerados por `scripts/gerar_dados.py`. Frases idênticas entre treino e teste: **0**.
- Limiar de confiança para revisão humana: 55%.

### Categoria (modelo de NLP)

| Métrica | Resultado |
|---|---|
| Acurácia | **87.5%** (56/64) |
| F1 macro | 0.871 |
| Relatos enviados para revisão humana | 17 (27%) |
| Acurácia nos decididos automaticamente | **91.5%** (43/47) |
| Erros de categoria que caíram na revisão humana | 4 de 8 |

Relatório por classe:

```
                        precision    recall  f1-score   support

   alagamento_drenagem       0.86      0.75      0.80         8
           arvore_poda       1.00      0.88      0.93         8
   buraco_pavimentacao       0.86      0.75      0.80         8
calcada_acessibilidade       0.80      1.00      0.89         8
    iluminacao_publica       1.00      1.00      1.00         8
          lixo_entulho       0.80      1.00      0.89         8
                outros       1.00      0.62      0.77         8
  sinalizacao_transito       0.80      1.00      0.89         8

              accuracy                           0.88        64
             macro avg       0.89      0.88      0.87        64
          weighted avg       0.89      0.88      0.87        64

```

Matriz de confusão (linha = real, coluna = previsto):

| real \ previsto | buraco | ilum | calcada | alag | lixo | arvore | sinal | outros |
|---|---|---|---|---|---|---|---|---|
| **buraco** | **6** | · | 1 | · | · | · | 1 | · |
| **ilum** | · | **8** | · | · | · | · | · | · |
| **calcada** | · | · | **8** | · | · | · | · | · |
| **alag** | 1 | · | 1 | **6** | · | · | · | · |
| **lixo** | · | · | · | · | **8** | · | · | · |
| **arvore** | · | · | · | · | · | **7** | 1 | · |
| **sinal** | · | · | · | · | · | · | **8** | · |
| **outros** | · | · | · | 1 | 2 | · | · | **5** |

### Urgência (regras explicáveis)

| Métrica | Resultado |
|---|---|
| Acerto exato (usando a categoria real) | **67.2%** (43/64) |
| Acerto com tolerância de 1 nível | 95.3% (61/64) |
| Acerto exato ponta a ponta (categoria prevista pela IA) | 67.2% |
| Casos CRÍTICOS identificados como críticos | **4/8** |
| Falsos críticos (marcado crítico sem ser) | 0 |
| Urgência subestimada (abaixo do esperado) | 8 |

### Todos os erros (para análise)

| Id | Relato | Esperado | Previsto | Conf. | Revisão? |
|---|---|---|---|---|---|
| V14 | A rua de terra virou lama e o ônibus não consegue subir | buraco | calcada | 66% | não |
| V15 | buraco perto da faixa de pedestre, um senhor de bengala quase caiu hoje | buraco | sinal | 86% | não |
| V27 | Bueiro aberto no meio da rua sem nenhuma sinalização, à noite não dá pra ver | alag | buraco | 48% | sim |
| V29 | O córrego está subindo muito rápido e tem gente tentando atravessar a ponte | alag | calcada | 31% | sim |
| V46 | Árvore bloqueando a visão da placa de pare do cruzamento | arvore | sinal | 72% | não |
| V58 | A escola municipal está sem merenda há uma semana | outros | alag | 28% | sim |
| V60 | Fogos de artifício todo fim de semana assustam os animais | outros | lixo | 23% | sim |
| V61 | A academia ao ar livre da praça está com aparelhos enferrujados | outros | lixo | 58% | não |

| Id | Relato | Urgência esperada | Regra deu |
|---|---|---|---|
| V04 | Os refletores da praça ficam ligados de dia e apagados de noite, tá invertido | baixa | media |
| V07 | Caixa de luz do poste aberta com os fios aparecendo, molecada brinca do lado | critica | media |
| V10 | Tem uns remendos no asfalto da minha rua que ficaram desnivelados | baixa | media |
| V12 | O chão da rua afundou de repente e abriu um buraco muito fundo, dá pra ver o can | critica | media |
| V16 | Buraquinho no asfalto na frente do número 50, só pra constar | baixa | media |
| V26 | Tampa de bueiro solta, quando passa carro ela pula | alta | media |
| V29 | O córrego está subindo muito rápido e tem gente tentando atravessar a ponte | critica | media |
| V32 | A rua alaga toda vez que chove forte e os carros ficam presos | alta | media |
| V36 | Alguém deixou um saco de lixo ao lado da lixeira cheia | baixa | media |
| V40 | Papel e folhas espalhados na praça depois da feira | baixa | media |
| V42 | Peço a poda dos galhos que estão batendo na janela do meu quarto | baixa | media |
| V43 | Galho enorme rachou e está quase caindo em cima do ponto de ônibus | critica | alta |
| V45 | Os galhos da árvore estão encostando nos fios de energia | alta | media |
| V47 | Folhas da árvore entupindo a calha da minha casa | baixa | media |
| V55 | Semáforo da rua lateral está com a luz vermelha queimada | alta | media |
| V56 | Tachões da avenida arrancados e a pintura da faixa sumiu | media | alta |
| V57 | Quero agendar a castração do meu gato pela prefeitura | baixa | media |
| V58 | A escola municipal está sem merenda há uma semana | media | alta |
| V60 | Fogos de artifício todo fim de semana assustam os animais | baixa | media |
| V62 | Qual o telefone da subprefeitura? | baixa | media |
| V64 | Gostaria de sugerir mais linhas de ônibus para o bairro | baixa | media |

## Anexo: conjunto de DESENVOLVIMENTO (usado para ajustar as regras)

Na primeira versão (regras v1) este conjunto deu: categoria 93,1%, urgência exata 61,1% e só 5 de 8 casos críticos detectados. Os erros motivaram as regras v2. Como as regras foram ajustadas aqui, os números abaixo são otimistas; o resultado que vale é o da Parte A.

- Amostra: **72 relatos** escritos à mão, 9 por categoria, com categoria e urgência esperadas (`dados/teste/casos_desenvolvimento.csv`).
- Base de treino: 880 relatos sintéticos gerados por `scripts/gerar_dados.py`. Frases idênticas entre treino e teste: **0**.
- Limiar de confiança para revisão humana: 55%.

### Categoria (modelo de NLP)

| Métrica | Resultado |
|---|---|
| Acurácia | **93.1%** (67/72) |
| F1 macro | 0.931 |
| Relatos enviados para revisão humana | 15 (21%) |
| Acurácia nos decididos automaticamente | **96.5%** (55/57) |
| Erros de categoria que caíram na revisão humana | 3 de 5 |

Relatório por classe:

```
                        precision    recall  f1-score   support

   alagamento_drenagem       1.00      1.00      1.00         9
           arvore_poda       0.89      0.89      0.89         9
   buraco_pavimentacao       1.00      0.89      0.94         9
calcada_acessibilidade       0.80      0.89      0.84         9
    iluminacao_publica       0.89      0.89      0.89         9
          lixo_entulho       0.90      1.00      0.95         9
                outros       1.00      0.89      0.94         9
  sinalizacao_transito       1.00      1.00      1.00         9

              accuracy                           0.93        72
             macro avg       0.93      0.93      0.93        72
          weighted avg       0.93      0.93      0.93        72

```

Matriz de confusão (linha = real, coluna = previsto):

| real \ previsto | buraco | ilum | calcada | alag | lixo | arvore | sinal | outros |
|---|---|---|---|---|---|---|---|---|
| **buraco** | **8** | · | 1 | · | · | · | · | · |
| **ilum** | · | **8** | 1 | · | · | · | · | · |
| **calcada** | · | · | **8** | · | · | 1 | · | · |
| **alag** | · | · | · | **9** | · | · | · | · |
| **lixo** | · | · | · | · | **9** | · | · | · |
| **arvore** | · | 1 | · | · | · | **8** | · | · |
| **sinal** | · | · | · | · | · | · | **9** | · |
| **outros** | · | · | · | · | 1 | · | · | **8** |

### Urgência (regras explicáveis)

| Métrica | Resultado |
|---|---|
| Acerto exato (usando a categoria real) | **90.3%** (65/72) |
| Acerto com tolerância de 1 nível | 100.0% (72/72) |
| Acerto exato ponta a ponta (categoria prevista pela IA) | 90.3% |
| Casos CRÍTICOS identificados como críticos | **8/8** |
| Falsos críticos (marcado crítico sem ser) | 1 |
| Urgência subestimada (abaixo do esperado) | 1 |

### Todos os erros (para análise)

| Id | Relato | Esperado | Previsto | Conf. | Revisão? |
|---|---|---|---|---|---|
| T01 | Cabo de energia arrebentou com o vento e está caído no chão da calçada, as crian | ilum | calcada | 47% | sim |
| T15 | rua toda esburacada, parece queijo suíço, moto cai direto | buraco | calcada | 46% | sim |
| T22 | A raiz da árvore levantou a calçada inteira em frente ao prédio | calcada | arvore | 78% | não |
| T53 | A copa da árvore está tampando a luz do poste e a rua fica escura | arvore | ilum | 63% | não |
| T71 | Estão construindo um puxadinho irregular no terreno ao lado | outros | lixo | 28% | sim |

| Id | Relato | Urgência esperada | Regra deu |
|---|---|---|---|
| T17 | Os paralelepípedos da ladeira soltaram e os carros derrapam | media | alta |
| T35 | Vazamento de água limpa na rua faz dois dias, desperdiçando | media | baixa |
| T44 | Caçamba de entulho estacionada há duas semanas ocupando a vaga | baixa | media |
| T51 | As raízes da árvore estão rachando o muro da escola | media | alta |
| T53 | A copa da árvore está tampando a luz do poste e a rua fica escura | media | alta |
| T61 | Farol piscando amarelo desde ontem no cruzamento movimentado | alta | critica |
| T72 | A internet e o sinal de celular caem toda hora no bairro | baixa | media |

## Parte B: execução ponta a ponta e casos de falha

| # | Cenário | O que foi feito | Resultado observado | OK? |
|---|---|---|---|---|
| 1 | Execução normal (lote de demonstração) | 3 canais, 22 linhas com erros propositais | 16 novos, 5 em quarentena, 1 duplicado, 3 para revisão, 1 com CPF/telefone removido, 17 e-mails gerados | ✅ |
| 2 | Idempotência: o mesmo lote chega de novo | reprocessar os mesmos arquivos | 0 novos, 16 já processados ignorados, 0 e-mail repetido (só o relatório da nova execução) | ✅ |
| 3 | Arquivo corrompido e arquivo sem as colunas esperadas | Excel inválido + CSV com colunas erradas junto com o lote bom | rejeitados ['sp156_sem_colunas.csv', 'subprefeitura_corrompida.xlsx'], movidos para entrada/com_erro; os outros arquivos geraram 16 protocolos | ✅ |
| 4 | Nenhum arquivo na entrada | rodar o robô com a pasta vazia | status 'concluido', avisos para 3 canais, relatório gerado | ✅ |
| 5 | API do app Zelo e Open-Meteo fora do ar | endereços que recusam conexão | app: não usada: lido o arquivo exportado (app_zelo_*.json); chuva: indisponível (seguiu sem chuva); 16 protocolos gerados mesmo assim | ✅ |
| 6 | Open-Meteo instável (2 respostas HTTP 503) e depois 35 mm de chuva | servidor local imitando a API | retry com espera recuperou a resposta (14 chamadas); 3 alagamento(s)/árvore(s) com urgência elevada pela chuva | ✅ |
| 7 | Servidor de e-mail fora do ar | SMTP em porta sem servidor | 17 e-mails ficaram 'pendente' com o .eml guardado; a execução terminou normalmente | ✅ |
| 8 | Servidor de e-mail volta na execução seguinte | SMTP local de teste ligado | 18 mensagens entregues (17 pendentes + relatório novo), sem duplicar | ✅ |
| 9 | Arquivo do modelo de IA corrompido | substituir o .joblib por lixo | robô detectou, retreinou e seguiu (16 protocolos) | ✅ |
| 10 | Dados pessoais no log | procurar CPF, telefone e e-mail do lote no robo.log | nenhum dado pessoal encontrado no log | ✅ |

### Trechos de log dos cenários

**Cenário 1: Execução normal (lote de demonstração)** (trecho do log)

```
2026-11-18 14:09:33,445 | WARNING | zelo.ingestao      | 20261118-140933-399 | Quarentena: sp156/SP156-88237 -> descrição vazia ou curta demais (< 15 caracteres)
2026-11-18 14:09:33,445 | WARNING | zelo.ingestao      | 20261118-140933-399 | Quarentena: sp156/SP156-88238 -> data de abertura inválida
2026-11-18 14:09:33,445 | WARNING | zelo.ingestao      | 20261118-140933-399 | Quarentena: subprefeitura/SUB-CL-0416 -> descrição vazia ou curta demais (< 15 caracteres)
2026-11-18 14:09:33,445 | WARNING | zelo.ingestao      | 20261118-140933-399 | Quarentena: app_zelo/ZL-2026-000144 -> bairro não reconhecido
2026-11-18 14:09:33,450 | INFO    | zelo.ingestao      | 20261118-140933-399 | 1 relato(s) duplicado(s) no lote foram descartados
2026-11-18 14:09:33,516 | INFO    | zelo.robo          | 20261118-140933-399 | 16 nova(s) solicitação(ões): 13 encaminhada(s), 3 para revisão humana
```

**Cenário 2: Idempotência: o mesmo lote chega de novo** (trecho do log)

```
2026-11-18 14:09:33,730 | INFO    | zelo.robo          | 20261118-140933-702 | 16 relato(s) já processado(s) antes foram ignorados (idempotência)
```

**Cenário 3: Arquivo corrompido e arquivo sem as colunas esperadas** (trecho do log)

```
2026-11-18 14:09:33,760 | ERROR   | zelo.ingestao      | 20261118-140933-746 | Arquivo rejeitado: sp156_sem_colunas.csv: colunas obrigatórias ausentes ['NUM_SOLICITACAO', 'DATA_ABERTURA', 'DISTRITO', 
2026-11-18 14:09:33,767 | ERROR   | zelo.ingestao      | 20261118-140933-746 | Arquivo rejeitado: subprefeitura_corrompida.xlsx: Excel ilegível (BadZipFile)
```

**Cenário 4: Nenhum arquivo na entrada** (trecho do log)

```
2026-11-18 14:09:33,984 | WARNING | zelo.ingestao      | 20261118-140933-976 | Canal 'sp156' sem arquivo na entrada (sp156_*.csv). Seguindo com os demais.
2026-11-18 14:09:33,984 | WARNING | zelo.ingestao      | 20261118-140933-976 | Canal 'subprefeitura' sem arquivo na entrada (subprefeitura_*.xlsx). Seguindo com os demais.
2026-11-18 14:09:33,984 | WARNING | zelo.ingestao      | 20261118-140933-976 | Canal 'app_zelo' sem arquivo na entrada (app_zelo_*.json). Seguindo com os demais.
```

**Cenário 5: API do app Zelo e Open-Meteo fora do ar** (trecho do log)

```
2026-11-18 14:09:34,115 | WARNING | zelo.apis          | 20261118-140934-001 | Open-Meteo: ConnectionError na tentativa 1/3
2026-11-18 14:09:34,166 | WARNING | zelo.apis          | 20261118-140934-001 | Open-Meteo: ConnectionError na tentativa 2/3
2026-11-18 14:09:34,268 | WARNING | zelo.apis          | 20261118-140934-001 | Open-Meteo: ConnectionError na tentativa 3/3
2026-11-18 14:09:34,268 | WARNING | zelo.apis          | 20261118-140934-001 | Open-Meteo indisponível após 3 tentativa(s): ConnectionError. Este bairro fica sem contexto de chuva.
2026-11-18 14:09:34,269 | WARNING | zelo.apis          | 20261118-140934-001 | Open-Meteo: ConnectionError na tentativa 1/3
2026-11-18 14:09:34,321 | WARNING | zelo.apis          | 20261118-140934-001 | Open-Meteo: ConnectionError na tentativa 2/3
2026-11-18 14:09:34,422 | WARNING | zelo.apis          | 20261118-140934-001 | Open-Meteo: ConnectionError na tentativa 3/3
2026-11-18 14:09:34,422 | ERROR   | zelo.apis          | 20261118-140934-001 | Open-Meteo indisponível após 3 tentativa(s): ConnectionError. Seguindo SEM contexto de chuva nesta execução.
```

**Cenário 6: Open-Meteo instável (2 respostas HTTP 503) e depois 35 mm de chuva** (trecho do log)

```
2026-11-18 14:09:34,697 | WARNING | zelo.apis          | 20261118-140934-642 | Open-Meteo: HTTP 503 na tentativa 1/3
2026-11-18 14:09:34,749 | WARNING | zelo.apis          | 20261118-140934-642 | Open-Meteo: HTTP 503 na tentativa 2/3
```

**Cenário 7: Servidor de e-mail fora do ar** (trecho do log)

```
2026-11-18 14:09:38,125 | WARNING | zelo.email         | 20261118-140935-388 | SMTP falhou na tentativa 1/3: ConnectionRefusedError: [Errno 111] Connection refused
2026-11-18 14:09:38,176 | WARNING | zelo.email         | 20261118-140935-388 | SMTP falhou na tentativa 2/3: ConnectionRefusedError: [Errno 111] Connection refused
2026-11-18 14:09:38,277 | WARNING | zelo.email         | 20261118-140935-388 | SMTP falhou na tentativa 3/3: ConnectionRefusedError: [Errno 111] Connection refused
```

**Cenário 8: Servidor de e-mail volta na execução seguinte** (trecho do log)

```
2026-11-18 14:09:38,394 | INFO    | zelo.email         | 20261118-140938-284 | 17 e-mail(s) pendente(s) de execuções anteriores reenviado(s)
```

**Cenário 8: assuntos recebidos pelo SMTP local (amostra)**

- Zelo | Protocolo ZR-2026-000001 recebido
- Zelo | Protocolo ZR-2026-000002 recebido
- Zelo | Protocolo ZR-2026-000004 recebido
- Zelo | Protocolo ZR-2026-000005 recebido
- ... e mais 14

**Cenário 9: Arquivo do modelo de IA corrompido** (trecho do log)

```
2026-11-18 14:09:38,944 | WARNING | zelo.ia            | 20261118-140938-907 | Modelo inválido (pop from empty list). Treinando novamente.
2026-11-18 14:09:39,201 | INFO    | zelo.ia            | 20261118-140938-907 | Modelo treinado com 880 exemplos e salvo em classificador.joblib
```

