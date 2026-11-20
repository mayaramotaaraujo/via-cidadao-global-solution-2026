# Resumo das métricas do Zelo

## STT: comparação de modelos (20 áudios)

| Modelo | Áudios | WER | Latência média (s) | Latência p90 (s) | RTF |
|---|---|---|---|---|---|
| base | 20 | 33.6% | 0.46 | 0.47 | 0.113 |
| small | 20 | 16.6% | 1.40 | 1.45 | 0.345 |


## STT: análise de viés (WER por grupo)

| Modelo | Dimensão | Grupo | Áudios | WER |
|---|---|---|---|---|
| base | faixa_etaria | 18-29 | 14 | 30.7% |
| base | faixa_etaria | 60+ | 6 | 39.0% |
| base | falante | F1 | 7 | 27.8% |
| base | falante | F2 | 7 | 33.8% |
| base | falante | F3 | 6 | 39.0% |
| base | genero | feminino | 7 | 33.8% |
| base | genero | masculino | 7 | 27.8% |
| base | genero | nao_informado | 6 | 39.0% |
| base | ruido | nao | 15 | 27.4% |
| base | ruido | sim | 5 | 52.8% |
| small | faixa_etaria | 18-29 | 14 | 18.6% |
| small | faixa_etaria | 60+ | 6 | 13.0% |
| small | falante | F1 | 7 | 16.7% |
| small | falante | F2 | 7 | 20.6% |
| small | falante | F3 | 6 | 13.0% |
| small | genero | feminino | 7 | 20.6% |
| small | genero | masculino | 7 | 16.7% |
| small | genero | nao_informado | 6 | 13.0% |
| small | ruido | nao | 15 | 11.6% |
| small | ruido | sim | 5 | 32.1% |


## LLM e diálogo (30 perguntas)

| Modelo | Acerto no tema (25) | Continuação (5) | Admite não saber (2) | Recusas adequadas (5) | Geral (30) | Latência LLM (s) |
|---|---|---|---|---|---|---|
| openai:gpt-4o-mini | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 1.07 |


## TTS (10 amostras)

| Avaliadores | Avaliações | Naturalidade (1-5) | DP | Clareza (1-5) | DP |
|---|---|---|---|---|---|
| 3 | 30 | 4.27 | 0.69 | 4.47 | 0.57 |


| Amostra | Naturalidade | Clareza |
|---|---|---|
| 1 | 4.33 | 4.33 |
| 2 | 4.67 | 5.0 |
| 3 | 4.0 | 4.67 |
| 4 | 4.67 | 4.0 |
| 5 | 3.33 | 4.67 |
| 6 | 4.33 | 4.33 |
| 7 | 4.67 | 5.0 |
| 8 | 4.0 | 4.67 |
| 9 | 4.33 | 3.67 |
| 10 | 4.33 | 4.33 |


## Ponta a ponta (10 conversas, 30 turnos): latência em segundos

| Etapa | Média | Mediana | p90 | Máx |
|---|---|---|---|---|
| stt | 1.46 | 1.43 | 1.55 | 1.75 |
| rag | 0.00 | 0.00 | 0.00 | 0.00 |
| llm | 1.10 | 1.06 | 1.23 | 2.26 |
| adapt | 0.00 | 0.00 | 0.00 | 0.00 |
| tts | 3.04 | 2.71 | 3.85 | 17.09 |
| total | 5.60 | 5.21 | 7.05 | 19.38 |
