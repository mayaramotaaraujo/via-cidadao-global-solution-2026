Olhamos as 12 imagens de cada tipo de erro em que o modelo estava mais seguro: os falsos positivos de probabilidade mais alta (0,91 a 0,94) e os falsos negativos de probabilidade mais baixa (0,06 a 0,08). Elas não representam todos os erros, porque boa parte deles ficou perto do limiar, mas mostram os casos em que o modelo errou com mais convicção.

**Falsos negativos (havia fissura e o modelo não viu).**

* Onze das doze imagens são de pavimentos, e onze vêm de apenas três fotos de origem (011, 018 e 023). O erro ficou concentrado em poucas fotos.
* A superfície nessas imagens é bege, rugosa e cheia de pedriscos. A fissura é uma linha fina e de pouco contraste, que se mistura com a textura. Isso aparece em recortes como 011-66 e 018-20.
* Em outros recortes dessas fotos (023-46, 023-52 e 023-85) só vemos pedras soltas e pequenas sombras, e não conseguimos enxergar uma fissura. Pode ser uma fissura muito fina ou um problema no rótulo, e não conseguimos concluir qual dos dois.
* No recorte W_7100-2, a parede azulada tem pontos azuis e uma linha muito fraca.

**Falsos positivos (a base diz que não há fissura e o modelo viu).**

* Vários recortes marcados como sem fissura na base parecem ter uma fissura visível. D_7054-1, D_7054-2, D_7054-9 e D_7034-1 mostram uma linha escura e contínua. Por isso, parte desses falsos positivos pode ser erro de rótulo da base e não erro do modelo. Não conseguimos afirmar isso sozinhos, porque seria preciso que outra pessoa revisasse as imagens.
* Em P_043-12 aparece uma emenda ou borda entre placas, com sombra. Em W_7102-3 aparece uma cavidade com perda de material, que é um dano de outro tipo e não uma fissura. D_7037-1 tem linhas finas retas em ângulo, que parecem marcações.
* Os recortes D_7002-2, W_7080-5, W_7089-1 e W_7094-2 têm linhas muito fracas, e W_7112-6 só tem manchas escuras, sem linha clara.

**O que isso mostra.**

* O desempenho depende bastante de poucas fotos. O teste tem apenas 34 fotos de origem, e os erros mais fortes se repetem nas mesmas fotos (onze de doze falsos negativos em três fotos, e três falsos positivos da foto 7054). Isso reforça que os números têm margem de variação grande.
* A precisão pode estar sendo subestimada, se parte dos falsos positivos for fissura que a base não marcou.
* O modelo tem mais dificuldade em pavimentos de textura rugosa, onde a fissura fina se confunde com o fundo. Já emendas, bordas e cavidades foram confundidas com fissura, o que para a triagem não é grave, porque esses pontos também podem merecer o olhar de um inspetor.
