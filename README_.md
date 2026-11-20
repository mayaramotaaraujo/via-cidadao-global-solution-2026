# VIA CIDADÃO: Global Solution 2026.2 (CitizenTech)


## Sobre o projeto

O VIA CIDADÃO é uma plataforma de zeladoria urbana. A ideia é ajudar o poder público a receber, entender e priorizar problemas da cidade, como fissuras em calçadas, e ajudar pessoas com deficiência auditiva a perceber sons importantes. Cada disciplina da Global Solution desenvolveu uma parte do projeto.

## Estrutura do repositório

| Pasta | Disciplina | O que tem |
|---|---|---|
| `governanca/` | Governança em IA e Business Analytics | Relatório em PDF e Word, figura da arquitetura e scripts que geram o documento |
| `visao-computacional/` | Visão Computacional | Modelo que detecta fissuras em fotos de concreto, relatório e métricas |
| `ia-generativa/` | Generative AI | Assistente com busca em fontes, relatório e testes |
| `physical-computing/` | Physical Computing | OuviAí: modelo de reconhecimento de sons treinado no Edge Impulse, dados de teste e relatório |
| `cluster/` | Cluster Computing | Relatório e script do dimensionamento da triagem de imagens |
| `ai-for-rpa/` | AI for RPA | Parte do Gabriel |
| `front-end-mobile/` | Front End & Mobile | Parte do Gabriel |
| `pln-chatbots/` | PLN e Chatbots | Parte do Gabriel |
| `computacao-quantica/` | Computação Quântica | Parte do Gabriel |

## Como os módulos se ligam

A foto de um problema passa pelo módulo de Visão Computacional, que gera uma ocorrência. O assistente da IA Generativa recebe essa ocorrência e devolve uma orientação com as fontes. O OuviAí reconhece três sons (campainha, batida na porta e ambiente) e mostra um alerta no celular. O Cluster estima o tempo de triagem de muitas imagens. A Governança reúne tudo, indica o que foi e o que não foi integrado, e analisa riscos, LGPD e indicadores. O detalhe está no relatório da pasta `governanca/`.

## Resultados principais

- Visão Computacional: precisão 0,452, revocação 0,877 e F1 0,597, com limiar 0,24.
- IA Generativa: 14 de 17 perguntas do teste respondidas corretamente.
- OuviAí: validação de 54,3%, 1 de 15 acertos no teste com arquivos e 12 de 15 nas tentativas ao vivo. São resultados fracos, explicados no relatório.
- Cluster: estimativa de 45,18 s com 2 workers e 22,84 s com 4 workers, por cálculo e não por simulação.

## Entregas

- Relatório: `governanca/relatorio_governanca.pdf`


## Observações

- Não há chaves de API nem dados pessoais no repositório.
- Os resultados são de testes feitos pelos autores e não de uso real.
