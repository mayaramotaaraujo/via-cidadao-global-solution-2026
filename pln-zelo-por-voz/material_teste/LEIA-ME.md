# Material de teste do Zelo

| Arquivo ou pasta | Conteúdo |
|---|---|
| `stt/roteiro_gravacao.csv` | as 20 frases de referência, com falante anonimizado (F1, F2, F3), faixa etária e presença de ruído |
| `stt/audios/` | os 20 áudios gravados pelo grupo, 5 deles com ruído real de fundo (TV, trânsito, música, conversa e ventilador) |
| `llm/perguntas_avaliacao.csv` | 30 perguntas com resposta esperada: 20 do tema (2 sem resposta na base), 5 de continuação e 5 fora do escopo |
| `tts/frases_tts.csv` | as 10 respostas sintetizadas para avaliação |
| `tts/audios/` | os 10 áudios gerados pelo TTS |
| `tts/avaliacao_tts.csv` | notas de 1 a 5 de naturalidade e clareza, dadas por 3 avaliadores |
| `e2e/conversas.csv` | as 10 conversas de 3 turnos usadas no teste ponta a ponta, cada uma com continuação e algumas com recusa |

Os falantes aparecem apenas por código, as frases são fictícias e não contêm dados pessoais, e os áudios foram gravados com o termo de consentimento em `docs/termo_consentimento_gravacao.md`. Os resultados de cada teste estão em `results/`.
