# Guia do OuviAí: o que fazer no celular e no Edge Impulse

Tempo estimado: 2 horas a 2h30. Faça na ordem. Os nomes dos botões do Edge Impulse podem mudar um pouco de lugar. Em caso de dúvida, vale o que o professor pediu e o que aparece na sua tela.

## Antes de começar
* Celular com microfone funcionando e navegador atualizado (Chrome no Android ou Safari no iPhone).
* Conta gratuita no Edge Impulse (studio.edgeimpulse.com). Crie o projeto com o nome OuviAi.
* Avise quem estiver em casa que você vai gravar sons. Não grave conversas que identifiquem pessoas.

## 1. Conectar o celular (5 min)
1. No Edge Impulse, vá em Devices, depois Connect a new device, depois Mobile phone.
2. Leia o QR code com a câmera do celular e abra o link.
3. Autorize o microfone. O celular deve aparecer na lista de dispositivos.

## 2. Gravar os áudios (40 a 50 min)
Regras: 3 classes, com estes nomes exatos nos rótulos (label): `campainha`, `batida_na_porta`, `ambiente`.
Cada classe precisa de 20 gravações de 5 segundos: 15 para Training e 5 para Test.

1. Vá em Data acquisition. Escolha o dispositivo (celular), o rótulo, **Sample length = 5000 ms** e a frequência de **16000 Hz**. Em Category, escolha Training ou Testing.
2. Grave primeiro as 15 de Training de cada classe, variando as condições:
   * campainha: campainhas diferentes (a da sua casa, de vídeos de campainha tocados em outro aparelho, aplicativo de som), distâncias diferentes, tocar uma ou duas vezes.
   * batida_na_porta: portas e superfícies diferentes (madeira, ferro, armário), batida fraca e forte, distâncias diferentes.
   * ambiente: ventilador, cozinha, rua, TV ou música sem fala identificável, silêncio, passos. Nada de conversa de pessoas reais.
3. Grave as 5 de Test de cada classe **em outro momento ou outro lugar**, com a Category em Testing. Esses arquivos nunca podem ir para o Training.
4. Ouça cada gravação (clique no arquivo). Se o evento não está no áudio, apague e grave de novo.
5. Confira em Data acquisition: 45 em Training e 15 em Testing, tudo com 5 s. Tire a **captura 01_data_acquisition**.
6. Anote no `dados/params.json`: origem dos áudios (como e onde você gravou) e qual celular e navegador usou.
7. (Se o professor pedir o WAV) O Edge Impulse permite baixar os arquivos. Eles devem estar em 16 kHz, mono, PCM16.

## 3. Impulse design (10 min)
1. Vá em Impulse design. Raw data: window size e window increase. Anote os valores que aparecerem (o tutorial do Edge Impulse usa 1000 ms e 300 ms como exemplo, mas use o que for razoável para áudios de 5 s e **copie os valores reais**).
2. Add a processing block: **Audio (MFE)**.
3. Add a learning block: **Classification**. Confirme que as 3 classes aparecem como saída.
4. Clique em Save Impulse. Tire a **captura 02_impulse_design**.
5. Anote em `params.json`: window size e window increase.

## 4. Generate features (5 a 10 min)
1. Vá no bloco MFE. Anote os parâmetros que aparecem (frame length, frame stride, filter number, FFT length, low frequency, high frequency, noise floor) em `params.json`.
2. Clique em Generate features e espere terminar.
3. Olhe o Feature explorer: as classes devem formar grupos. Tire a **captura 03_generate_features**.

## 5. Treinar a CNN (10 a 15 min)
1. Vá em Classifier. Anote número de épocas, taxa de aprendizado e a arquitetura (as camadas que aparecem). Se tiver opção, use camadas convolucionais 1D ou 2D, que formam a CNN.
2. Clique em Start training.
3. Quando terminar, anote a acurácia e a perda de validação e tire a **captura 04_classifier** com a matriz de confusão.
4. Se a acurácia ficar muito baixa, o melhor remédio costuma ser gravar mais exemplos variados, não mexer em muitos parâmetros. Guarde os parâmetros da versão final.

## 6. Testar com os arquivos de Test (15 min)
1. Vá em Model testing. Os 15 arquivos de Test aparecem, com o rótulo esperado.
2. Clique em Classify all.
3. Para cada arquivo, copie para `dados/teste_arquivos.csv` a classe prevista (`classe_prevista`) e a confiança exibida (`confianca_exibida`). Use os nomes exatos das classes.
4. Tire a **captura 05_model_testing**.
5. Em `dados/observacoes.md`, na seção de erros do teste, escreva o que errou e por que você acha que errou (som parecido, ruído, distância). Se não houve erro, escreva isso.

## 7. Validação ao vivo no celular (30 min)
1. Vá em Deployment, depois Run this model. Leia o QR code com o celular, abra no navegador e autorize o microfone.
2. O modelo roda no navegador e mostra a classe e a probabilidade em tempo real.
3. Faça **5 tentativas por classe, 15 no total** (campainha, batida, ambiente). Misture a ordem. Para cada tentativa, preencha em `dados/ao_vivo.csv`: som produzido, classe prevista, confiança exibida e uma observação.
4. Na classe ambiente, faça sons que podem confundir (conversa baixa sem identificar pessoas, objeto caindo, TV). Anote falsos positivos.
5. Grave a tela do celular em um vídeo curto, ou tire as capturas **06_run_model_celular**, 07_ao_vivo_1 e 08_ao_vivo_2.
6. Em `dados/observacoes.md`, escreva os erros ao vivo.

## 8. O que me enviar
* `dados/params.json`, `dados/teste_arquivos.csv`, `dados/ao_vivo.csv`, `dados/observacoes.md`
* As capturas 01 a 06 (e 07 e 08 se tiver), com os nomes do arquivo `capturas/LEIA-ME.txt`
* O link ou o vídeo da demonstração no celular

Com isso eu gero o relatório em PDF com tabelas, matrizes de confusão, percentual de acerto e discussão. Se você preferir, também pode rodar você mesma: `python src/gerar_relatorio.py . --pdf`.

## Cuidados
* Probabilidade mostrada na tela não é acurácia. A acurácia vem de comparar a resposta com o som que você realmente produziu.
* Não reaproveite os arquivos de Test no Training.
* O OuviAí é educacional. Não é sistema de segurança nem de emergência.
