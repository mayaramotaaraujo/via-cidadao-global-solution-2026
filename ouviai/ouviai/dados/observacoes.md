# Observações

## Erros no teste com arquivos
No teste com os 15 arquivos que não foram usados no treino, o modelo acertou 1 de 15. Em 13 arquivos o resultado mais frequente foi "incerto", ou seja, nenhuma classe passou de 60% de confiança nas janelas de 1 segundo. Em 1 arquivo de ambiente, a classe mais frequente foi batida na porta. O único acerto foi um áudio de campainha com apenas 1 segundo, que tem uma só janela e por isso é uma evidência fraca, além de ser mais curto que os 5 segundos pedidos.

Nos arquivos de batida na porta, entre 0 e 4 das 9 janelas foram classificadas como batida, e o restante ficou como incerto. Ou seja, o modelo reconheceu alguns trechos, mas não de forma firme.

Possíveis causas, que não chegamos a testar: cada janela de 1 segundo recebe o rótulo do arquivo inteiro, então janelas de silêncio dentro de um áudio de campainha ou de batida ficam parecidas com ambiente; o conjunto de treino é pequeno, com 15 áudios por classe; e os áudios de teste foram gravados em outro momento, com condições um pouco diferentes. A acurácia de validação do treino foi de 54,3%, bem acima da do teste, o que mostra que o modelo não generalizou bem. Decidimos entregar o modelo desta primeira rodada de treino, sem ajustes depois de ver o teste, para não usar os dados de teste no ajuste.

## Erros na validação ao vivo
Ao vivo no celular, o modelo acertou 12 de 15 tentativas, ou 80%. Os 3 erros foram todos na classe batida na porta: 2 tentativas ficaram como "No event detected" e 1 ficou como ambiente. Campainha e ambiente acertaram 5 de 5, e nenhuma das 5 tentativas de ambiente foi classificada como evento, então não houve falso positivo nessa classe.

Nas tentativas 9 e 10, as linhas da tabela do celular mostram janelas de batida com confiança de 0,80 a 0,92 pouco antes da resposta final, ou seja, o modelo chegou a reconhecer a batida, mas a classe exibida no fim mudou. Na tentativa 8, a maior confiança de batida foi 0,44, abaixo do limiar de 0,60.

O resultado ao vivo foi melhor que o do teste com arquivos, e não sabemos a causa com certeza. Uma explicação possível é a diferença no jeito de medir: o teste confere cada janela com o limiar de 60%, e ao vivo lemos a classe mostrada no topo da tela, sem exigir que todas as janelas acertem. Não testamos essa explicação. Como foram só 5 tentativas por classe, um erro a mais ou a menos muda o resultado da classe em 20 pontos percentuais.

## Origem dos áudios
Veja o campo de origem dos áudios no relatório.
