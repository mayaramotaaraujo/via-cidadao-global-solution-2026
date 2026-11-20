# VIA CIDADÃO: assistente

Assistente de conversa do módulo VIA INTELIGÊNCIA que responde dúvidas sobre como pedir serviços da prefeitura e sobre acessibilidade, usando só uma base de fontes cadastradas, e mostra a fonte de cada resposta.

Integrantes: Mayara Mota (RM 563887) e Gabriel Palmeira (RM 563522).


## Pastas

| Pasta | Conteúdo |
|---|---|
| data/corpus | 8 fichas de fontes, com URL e data de consulta no cabeçalho |
| src/chunking.py | leitura dos documentos e divisão em trechos |
| src/retriever.py | busca lexical (BM25), vetorial (TF IDF) e híbrida |
| src/gerador.py | prompt do sistema e geração (extrativa ou com modelo de linguagem) |
| src/protecoes.py | filtro de injeção, dados pessoais, emergência e conferência de números |
| src/pipeline.py | fluxo completo do assistente |
| src/integracao.py | ligação com a ocorrência do VIA CIDADÃO |
| src/avaliar.py | todos os testes |
| tests/ | perguntas de teste e documentos de teste com ordens escondidas |
| docs/ | relatório de avaliação, anexo com o registro dos testes e roteiro do vídeo |
| results/ | resultados em JSON de cada rodada |

## Configuração usada

Chunking por seção com máximo de 700 caracteres e overlap de 1 frase. Busca híbrida (BM25 com TF IDF de n gramas de caracteres, unidos por Reciprocal Rank Fusion). Top k igual a 5. Limiar de cobertura 0,30. No modo com modelo de linguagem (Gemini, modelo gemini-3.8-flash) o único parâmetro fixado é o máximo de 1024 tokens de resposta.

## Avisos

A avaliação deste repositório foi rodada só com o gerador extrativo. O modo com modelo de linguagem está implementado, mas a avaliação completa não foi concluída porque o limite diário gratuito da API do Gemini acabou (20 chamadas por dia por modelo). As fichas da base são resumos escritos pelo grupo e precisam de conferência com os textos oficiais, principalmente as leis. Os resultados e os limites estão no relatório em docs/relatorio_avaliacao.md.
