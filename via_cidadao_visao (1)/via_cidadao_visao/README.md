# VIA CIDADÃO: módulo VIA VISÃO (Visão Computacional)

Integrantes: Mayara Mota (RM 563887) e Gabriel Palmeira (RM 563522).

Classifica recortes de superfícies de concreto (pavimento, parede e tabuleiro de ponte) em com fissura e sem fissura, usando transferência de aprendizado. O resultado serve para triagem de inspeção. Fissura na imagem não diz se ela é grave nem se a estrutura é segura.

## Como rodar

O jeito mais simples é o notebook `notebooks/via_visao.ipynb` no Google Colab com GPU. Pela linha de comando:

1. `pip install -r requirements.txt`
2. Treino e avaliação: `python src/treinar.py --raiz CAMINHO_DA_SDNET2018 --saida results`
3. Relatório com os números medidos: `python src/gerar_relatorio.py results docs/relatorio_visao.md`
4. Tela: `streamlit run app/triagem.py` (precisa de `results/modelo.pt`)
5. Teste do código sem a base real: `python src/treinar.py --sintetico --sem-pesos --epocas 1 --saida results_teste` (os números desse teste não valem para a entrega) e `python tests/teste_video.py`

## Pastas

| Pasta | Conteúdo |
|---|---|
| src/dados.py | leitura da base, divisão por foto de origem, checagem de vazamento, amostragem |
| src/modelo.py | MobileNetV3 small e ResNet18, treino |
| src/avaliacao.py | métricas, escolha do limiar, exportação dos erros, latência e FPS |
| src/video.py | imagem, sequência e vídeo em grade de recortes, com confirmação de evento |
| src/sequencia.py | sequência simulada com recortes do teste, com resposta conhecida |
| src/ocorrencia.py | ocorrência no formato do VIA CIDADÃO |
| src/gerar_relatorio.py | monta o relatório só com números medidos |
| app/triagem.py | tela Streamlit |
| notebooks | notebook do Colab |
| docs | relatório e roteiro do vídeo |

## Base de dados

SDNET2018, licença CC BY 4.0, https://digitalcommons.usu.edu/all_datasets/48/ (DOI 10.15142/T3TD19). O download não está neste repositório.

## Avisos

O código foi testado com dados falsos. Os números reais só existem depois de rodar o treino com a SDNET2018. A regra que usa o número antes do traço no nome do arquivo como identificador da foto precisa ser conferida na tabela de grupos que o treino imprime.
