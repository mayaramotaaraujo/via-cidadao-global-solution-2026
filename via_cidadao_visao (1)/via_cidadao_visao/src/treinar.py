"""Fluxo completo do VIA VISÃO: preparar dados, treinar dois modelos, avaliar e medir latência.

Exemplo no Colab (GPU):
    python src/treinar.py --raiz /content/SDNET2018 --saida results

Teste rápido com dados falsos (não vale para o relatório):
    python src/treinar.py --sintetico --sem-pesos --epocas 1 --saida results_teste
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dados  # noqa: E402
import modelo as mod  # noqa: E402
from avaliacao import (curvas, distribuicao_erros, escolher_limiar, exportar_erros,  # noqa: E402
                       medir_latencia, metricas, por_superficie)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", help="pasta da SDNET2018 (com D, P e W)")
    ap.add_argument("--saida", default="results")
    ap.add_argument("--modelos", nargs="+", default=list(mod.ARQUITETURAS))
    ap.add_argument("--epocas", type=int, default=4)
    ap.add_argument("--tamanho", type=int, default=224, help="lado da entrada da rede em pixels")
    ap.add_argument("--lote", type=int, default=32)
    ap.add_argument("--max-treino", type=int, default=12000)
    ap.add_argument("--max-val", type=int, default=4000)
    ap.add_argument("--max-teste", type=int, default=6000)
    ap.add_argument("--revocacao-minima", type=float, default=0.90,
                    help="revocação mínima exigida na validação ao escolher o limiar")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--sem-pesos", action="store_true", help="não baixa pesos da ImageNet (só para teste)")
    ap.add_argument("--sintetico", action="store_true", help="usa dados falsos (só para teste)")
    a = ap.parse_args()

    torch.manual_seed(a.semente)
    np.random.seed(a.semente)
    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)

    raiz = a.raiz
    if a.sintetico:
        from sintetico import criar_base_falsa
        raiz = criar_base_falsa(saida / "base_falsa")
    if not raiz:
        ap.error("informe --raiz ou use --sintetico")

    # Atividade 1: exame dos dados e divisão por foto
    todos = dados.listar_imagens(raiz)
    print("Conferência dos grupos (recortes por foto de origem):")
    print(dados.conferir_grupos(todos))
    dividido = dados.dividir_por_foto(todos, semente=a.semente)
    base = dados.amostrar(dividido, a.max_treino, a.max_val, a.max_teste, semente=a.semente)
    resumo_dados = {
        "base_completa": {"recortes": int(len(todos)), "fotos": int(todos["foto"].nunique()),
                          "com_fissura": int(todos["rotulo"].sum())},
        "conferencia_grupos": dados.conferir_grupos(todos).reset_index().to_dict("records"),
        "usado": dados.resumo_conjuntos(base),
        "sintetico": bool(a.sintetico),
        "vazamento_entre_conjuntos": False,
    }
    dados.verificar_vazamento(base)
    (saida / "dados.json").write_text(json.dumps(resumo_dados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumo_dados["usado"], ensure_ascii=False, indent=2))

    tr = base[base["conjunto"] == "treino"]
    va = base[base["conjunto"] == "validacao"].reset_index(drop=True)
    te = base[base["conjunto"] == "teste"].reset_index(drop=True)
    disp = mod.escolher_dispositivo()
    print("Dispositivo:", disp)

    resultados, melhor_nome, melhor_f1_val, melhor_ck = {}, None, -1, None
    for nome in a.modelos:
        print(f"\n=== {nome} ===")
        m = mod.criar_modelo(nome, pesos=not a.sem_pesos)
        m, hist = mod.treinar(m, tr, va, a.tamanho, disp, epocas=a.epocas, lote=a.lote,
                              workers=a.workers)

        # Atividade 3: limiar escolhido na validação, métricas medidas no teste
        p_va = mod.prever_probs(m, va, a.tamanho, disp, workers=a.workers)
        limiar, _ = escolher_limiar(va["rotulo"], p_va, a.revocacao_minima)
        limiar_f1, _ = escolher_limiar(va["rotulo"], p_va, None)
        p_te = mod.prever_probs(m, te, a.tamanho, disp, workers=a.workers)
        pred = te.assign(prob=p_te)
        pred.to_csv(saida / f"predicoes_teste_{nome}.csv", index=False)

        r = {
            "parametros": mod.contar_parametros(m),
            "historico": hist,
            "limiar_escolhido": limiar,
            "limiar_melhor_f1": limiar_f1,
            "validacao": metricas(va["rotulo"], p_va, limiar),
            "teste_limiar_escolhido": metricas(te["rotulo"], p_te, limiar),
            "teste_limiar_0_5": metricas(te["rotulo"], p_te, 0.5),
            "teste_limiar_melhor_f1": metricas(te["rotulo"], p_te, limiar_f1),
            "teste_curvas": curvas(te["rotulo"], p_te),
            "teste_por_superficie": por_superficie(pred, limiar),
            "erros": distribuicao_erros(pred, limiar),
            "latencia": medir_latencia(m, te, a.tamanho, disp),
        }
        r["erros_exportados"] = exportar_erros(pred, limiar, saida / "erros" / nome)
        resultados[nome] = r

        f1_val = r["validacao"]["f1"]
        print(f"limiar {limiar:.2f}  teste: {r['teste_limiar_escolhido']}")
        print("latência:", r["latencia"])
        if f1_val > melhor_f1_val:
            melhor_nome, melhor_f1_val = nome, f1_val
            melhor_ck = {"arquitetura": nome, "estado": {k: v.cpu() for k, v in m.state_dict().items()},
                         "limiar": limiar, "tamanho": a.tamanho}

    # O modelo final é escolhido pelo F1 na VALIDAÇÃO, nunca pelo teste.
    torch.save(melhor_ck, saida / "modelo.pt")
    final = {
        "modelo_escolhido": melhor_nome,
        "criterio_escolha": "maior F1 na validação, com o limiar escolhido para revocação mínima na validação",
        "revocacao_minima_validacao": a.revocacao_minima,
        "tamanho_entrada": a.tamanho, "epocas": a.epocas, "lote": a.lote,
        "semente": a.semente, "sintetico": bool(a.sintetico), "sem_pesos_imagenet": bool(a.sem_pesos),
        "modelos": resultados,
    }
    (saida / "metricas.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nModelo escolhido: {melhor_nome}. Resultados em {saida}/metricas.json")


if __name__ == "__main__":
    main()
