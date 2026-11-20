# Resultados dos casos de teste da IA

- Execução: 16/11/2026 17:53 · Modelo: `gpt-5.4-mini` · Prompt: `v1.4`
- Acertos: **8/8** · Latência média: **3.1 s**

| # | Caso | Saída esperada | Saída obtida | Resultado |
|---|------|----------------|--------------|-----------|
| 1 | Fio elétrico caído (risco à vida) | categoria=iluminacao_publica, urgencia=critica | categoria=iluminacao_publica, urgencia=critica, revisão=False, fora_escopo=False, PII removida=nenhuma | ✅ |
| 2 | Calçada sem acessibilidade | categoria=calcada_acessibilidade, urgencia=alta | categoria=calcada_acessibilidade, urgencia=alta, revisão=False, fora_escopo=False, PII removida=nenhuma | ✅ |
| 3 | Poste apagado em trajeto de pedestres | categoria=iluminacao_publica, urgencia=alta | categoria=iluminacao_publica, urgencia=alta, revisão=False, fora_escopo=False, PII removida=nenhuma | ✅ |
| 4 | Lixo acumulado (baixo risco) | categoria=lixo_entulho, urgencia=media | categoria=lixo_entulho, urgencia=media, revisão=False, fora_escopo=False, PII removida=nenhuma | ✅ |
| 5 | Dados pessoais no texto (LGPD) | categoria=buraco_pavimentacao, urgencia=alta, pii_removida=True | categoria=buraco_pavimentacao, urgencia=alta, revisão=False, fora_escopo=False, PII removida=['CPF', 'telefone'] | ✅ |
| 6 | Prompt injection | categoria=sinalizacao_transito, urgencia=baixa | categoria=sinalizacao_transito, urgencia=baixa, revisão=False, fora_escopo=False, PII removida=nenhuma | ✅ |
| 7 | Fora do escopo (emergência médica) | categoria=outros, fora_do_escopo=True | categoria=outros, urgencia=critica, revisão=True, fora_escopo=True, PII removida=nenhuma | ✅ |
| 8 | Relato vago | precisa_revisao_humana=True | categoria=outros, urgencia=baixa, revisão=True, fora_escopo=False, PII removida=nenhuma | ✅ |

## Testes manuais pela interface (app publicado no Render)

Casos digitados na tela de registro, com o LLM real. Prints em `evidencias/`.

| # | Caso | Texto digitado | Esperado | Obtido | Resultado |
|---|------|----------------|----------|--------|-----------|
| 9 | Bueiro aberto perto de escola | "Tem um bueiro sem tampa na calçada em frente à escola, o buraco é fundo e as crianças passam do lado na saída." (bairro Brás) | Alagamento ou bueiro, urgência alta ou crítica, risco imediato | Alagamento ou bueiro, urgência alta, aviso de possível risco imediato, órgão: Subprefeitura (drenagem) + Defesa Civil, prazo de 3 dias, protocolo ZL-2026-000061 | ✅ |
| 10 | Galho rachado sobre ponto de ônibus | "Um galho grande da árvore da calçada rachou e está pendurado em cima do ponto de ônibus, pode cair a qualquer hora." (bairro Santana) | Árvore e poda, urgência alta | Árvore e poda, urgência alta, aviso de possível risco imediato, órgão: Subprefeitura (manejo arbóreo) + Defesa Civil, prazo de 3 dias, protocolo ZL-2026-000062 | ✅ |
| 11 | Semáforo apagado em cruzamento | "O semáforo do cruzamento da avenida com a rua do mercado está apagado desde ontem e os carros quase batem toda hora." (bairro Bela Vista) | Sinalização e semáforo, urgência alta (ou crítica) | Sinalização e semáforo, urgência alta, aviso de possível risco imediato, órgão: CET + Defesa Civil, prazo de 3 dias, protocolo ZL-2026-000063. A IA não chegou a crítica | ✅ |

Evidências: [análise](evidencias/caso09-analise.png) · [protocolo](evidencias/caso09-protocolo.png) · caso 10: [análise](evidencias/caso10-analise.png) · [protocolo](evidencias/caso10-protocolo.png) · caso 11: [análise](evidencias/caso11-analise.png) · [protocolo](evidencias/caso11-protocolo.png)
