#!/usr/bin/env bash
# Roda todas as avaliações em sequência e gera as tabelas do relatório.
# Uso: ./rodar_avaliacoes.sh        (com o ambiente virtual ativado)
set -e

echo "== 1/6 Testes unitários"
python -m pytest -q

echo "== 2/6 RAG (offline)"
python -m eval.eval_rag

echo "== 3/6 STT: Whisper base x small (precisa dos 20 áudios gravados)"
python -m eval.eval_stt --models base small || echo "STT pulado: grave os 20 áudios em material_teste/stt/audios"

echo "== 4/6 LLM: 30 perguntas"
python -m eval.eval_llm

echo "== 5/6 TTS: gerando os 10 áudios e a planilha de notas"
python -m eval.eval_tts gerar

echo "== 6/6 Ponta a ponta: 10 conversas x 3 turnos"
python -m eval.eval_e2e

python -m eval.gerar_tabelas
echo
echo "Pronto. Falta: 3 pessoas preencherem material_teste/tts/avaliacao_tts.csv e depois rodar"
echo "  python -m eval.eval_tts resumir && python -m eval.gerar_tabelas"
