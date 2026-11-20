# Relatório de execução do robô Zelo: 20261119-162556-795

- Status: **concluido_com_alertas**
- Início: 2026-11-19T16:25:56  |  Fim: 2026-11-19T16:26:04  |  Duração: 7.5 s
- Modo de e-mail: arquivo

## Números da execução

| Etapa | Quantidade |
|---|---|
| Linhas lidas (todos os canais) | 22 |
| Enviadas para quarentena (dado inválido) | 5 |
| Duplicadas no próprio lote | 1 |
| Já processadas em execuções anteriores | 0 |
| **Novas solicitações registradas** | **16** |
| Encaminhadas automaticamente | 13 |
| Na fila de revisão humana | 3 |
| Dados pessoais removidos de relatos | 1 |

## Integrações

| Integração | Situação |
|---|---|
| API do app Zelo | não usada: lido o arquivo exportado (app_zelo_*.json) |
| Open-Meteo (chuva) | ok |

## Arquivos de entrada

- OK: sp156_20261119.csv
- OK: subprefeitura_campo_limpo_20261119.xlsx
- OK: app_zelo_20261119.json

## Novas solicitações por urgência

| Urgência | Qtde |
|---|---|
| CRÍTICA | 2 |
| Alta | 7 |
| Média | 5 |
| Baixa | 2 |

## Despacho por órgão

| Órgão | Itens | Críticos |
|---|---|---|
| CET (Engenharia de Tráfego) | 1 | 0 |
| ILUME (Iluminação Pública) | 3 | 1 |
| SP Regula (Limpeza Urbana) | 2 | 0 |
| Subprefeitura Campo Limpo | 3 | 1 |
| Subprefeitura Capela do Socorro | 1 | 0 |
| Subprefeitura Penha | 1 | 0 |
| Subprefeitura Santana/Tucuruvi | 1 | 0 |
| Subprefeitura Sapopemba | 1 | 0 |

## Fila de revisão humana

| Protocolo | Motivo |
|---|---|
| ZR-2026-000007 | relato fora das categorias de zeladoria |
| ZR-2026-000012 | baixa confiança da IA (28%) |
| ZR-2026-000013 | relato fora das categorias de zeladoria |

## Quarentena

| Canal | Id de origem | Motivo |
|---|---|---|
| sp156 | SP156-88236 | bairro não reconhecido |
| sp156 | SP156-88237 | descrição vazia ou curta demais (< 15 caracteres) |
| sp156 | SP156-88238 | data de abertura inválida |
| subprefeitura | SUB-CL-0416 | descrição vazia ou curta demais (< 15 caracteres) |
| app_zelo | ZL-2026-000144 | bairro não reconhecido |

## E-mails

| Situação | Qtde |
|---|---|
| enviado | 0 |
| salvo_arquivo | 17 |
| pendente | 0 |
| ignorado_ja_enviado | 0 |
