"""Ponto de entrada do robô Zelo.

Uso:
    python main.py                       # processa o que estiver em entrada/
    python main.py --demo                # recria o lote de demonstração e processa
    python main.py --demo --simular-falha api smtp arquivo
    python main.py --resetar --demo      # apaga banco e saídas antes (demonstração limpa)
"""

from __future__ import annotations

import argparse
import shutil
import sys

from zelo_robo.config import Config
from zelo_robo.robo import executar


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Robô de triagem e despacho do Zelo (RPA + IA)")
    ap.add_argument("--demo", action="store_true",
                    help="gera o lote de demonstração em entrada/ antes de rodar")
    ap.add_argument("--resetar", action="store_true",
                    help="apaga banco, saídas e logs (começa do zero)")
    ap.add_argument("--simular-falha", nargs="+", default=[], choices=["api", "smtp", "arquivo"],
                    help="simula falhas previsíveis para demonstrar a resiliência")
    ap.add_argument("--nao-mover", action="store_true",
                    help="não move os arquivos lidos para entrada/processados")
    args = ap.parse_args(argv)

    cfg = Config.carregar()

    if args.resetar:
        cfg.caminho_banco.unlink(missing_ok=True)
        for pasta in (cfg.pasta_saida, cfg.pasta_logs,
                      cfg.pasta_entrada / "processados", cfg.pasta_entrada / "com_erro"):
            shutil.rmtree(pasta, ignore_errors=True)
        print("Banco, saídas e logs apagados.")

    if args.demo:
        from scripts.gerar_dados import gerar_lote_demo
        arquivos = gerar_lote_demo(cfg.pasta_entrada)
        print(f"Lote de demonstração criado: {', '.join(a.name for a in arquivos)}")

    if "api" in args.simular_falha:
        # Endereços que nunca respondem: força timeout/erro de conexão, retry e caminho seguro.
        cfg.clima_url = "https://api.open-meteo.invalid/v1/forecast"
        cfg.zelo_api_url, cfg.zelo_gestor_token = "https://zelo-api.invalid", "token-de-teste-123456"
        cfg.espera_retry_s = 0.2
    if "smtp" in args.simular_falha:
        cfg.email_modo, cfg.smtp_host, cfg.smtp_porta = "smtp", "smtp.invalid", 2525
        cfg.smtp_timeout_s, cfg.espera_retry_s = 3, 0.2
    if "arquivo" in args.simular_falha:
        cfg.pasta_entrada.mkdir(parents=True, exist_ok=True)
        (cfg.pasta_entrada / "subprefeitura_corrompida.xlsx").write_bytes(b"isto nao e um excel")
        (cfg.pasta_entrada / "sp156_sem_colunas.csv").write_text("A;B\n1;2\n", encoding="utf-8")

    resumo = executar(cfg, mover_arquivos=not args.nao_mover)

    c = resumo["contagens"]
    print("\n" + "=" * 64)
    print(f" Execução {resumo['run_id']}: {resumo['status'].upper()}")
    print(f" Lidos {c['lidos']} | novos {c['novos']} | encaminhados {c['encaminhados']} | "
          f"revisão humana {c['revisao_humana']} | quarentena {c['quarentena']}")
    print(f" Duplicados no lote {c['duplicados_no_lote']} | já processados antes {c['ja_processados']}")
    print(f" E-mails: {resumo['emails']}")
    print(f" Saídas em: {resumo['pasta_saida']}")
    print("=" * 64)
    return 1 if resumo["status"] == "falhou" else 0


if __name__ == "__main__":
    sys.exit(main())
