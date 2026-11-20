"""Orquestração do robô: entrada -> processamento com IA -> saída.

Cada etapa é isolada: se uma falha, ela é registrada no log e no relatório e o
robô continua com o que for possível. Só um erro que impeça QUALQUER resultado
(ex.: banco inacessível) marca a execução como "falhou".
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from datetime import datetime

import pandas as pd

from . import ingestao, integracoes
from .banco import Banco
from .classificador import Classificador
from .config import Config
from .email_envio import Carteiro
from .log import configurar_log
from .referencia import PRAZO_DIAS, coordenadas, email_do_orgao
from .regras import decidir
from .relatorio import ROTULO_CATEGORIA, gerar_despachos, gerar_relatorio, gerar_revisao

log = logging.getLogger("zelo.robo")


def _corpo_cidadao(l: dict) -> str:
    if l["status"] == "revisao_humana":
        situacao = "Situação: em análise por um servidor antes do encaminhamento\n"
    else:
        situacao = f"Encaminhado para: {l['orgao']}\n"
    return (
        "Olá!\n\n"
        f"Recebemos o seu relato de zeladoria urbana no bairro {l['bairro']}.\n\n"
        f"Protocolo: {l['protocolo']}\n"
        f"Tipo de problema: {ROTULO_CATEGORIA[l['categoria']]}\n"
        f"{situacao}"
        f"Prazo de referência: até {l['prazo_dias']} dia(s)\n\n"
        "A classificação foi feita automaticamente e pode ser revista por um servidor.\n"
        "Se houver risco imediato (fio caído, árvore caindo, alagamento com pessoas ilhadas),\n"
        "ligue para a Defesa Civil (199) ou para os Bombeiros (193).\n\n"
        "Você recebeu este e-mail porque autorizou o contato. Seu e-mail é apagado do nosso\n"
        "sistema depois deste envio.\n\n"
        "Robô Zelo | Protótipo acadêmico FIAP (dados fictícios)\n"
    )


def _corpo_orgao(orgao: str, itens: int, criticos: int, run_id: str) -> str:
    alerta = f"ATENÇÃO: {criticos} item(ns) CRÍTICO(S), com prazo de referência de 1 dia.\n\n" if criticos else ""
    return (
        f"Prezada equipe {orgao},\n\n"
        f"{alerta}Segue em anexo a lista de despacho da execução {run_id}, com {itens} solicitação(ões),\n"
        "ordenadas da mais urgente para a menos urgente. Os relatos já estão sem dados pessoais.\n"
        "A coluna 'Por que essa urgência' explica a regra aplicada em cada caso.\n\n"
        "Robô Zelo | Protótipo acadêmico FIAP (dados fictícios)\n"
    )


def executar(cfg: Config, mover_arquivos: bool = True) -> dict:
    cfg.garantir_pastas()
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    configurar_log(cfg.pasta_logs, run_id, cfg.nivel_log_console)
    inicio = time.monotonic()
    inicio_iso = datetime.now().isoformat(timespec="seconds")
    pasta_run = cfg.pasta_saida / run_id
    pasta_run.mkdir(parents=True, exist_ok=True)
    alertas: list[str] = []
    log.info("===== Robô Zelo: início da execução %s =====", run_id)

    banco = Banco(cfg.caminho_banco)
    banco.iniciar_execucao(run_id)
    integracoes_status: dict[str, str] = {}
    contagens = Counter()
    linhas_novas: list[dict] = []
    resumo_quarentena: list[dict] = []
    res = None
    status_final = "concluido"
    despachos: dict = {}
    arquivo_revisao = None
    revisao: list[dict] = []
    carteiro = Carteiro(cfg, banco, run_id, pasta_run / "outbox")

    try:
        # 1) API do app Zelo (com fallback para o arquivo exportado) -----------------
        df_app = None
        try:
            registros = integracoes.buscar_relatos_app(
                cfg.zelo_api_url, cfg.zelo_gestor_token, cfg.zelo_api_timeout_s, 2, cfg.espera_retry_s)
            df_app = ingestao.normalizar_app(registros, "API do app Zelo")
            integracoes_status["API do app Zelo"] = f"ok ({len(df_app)} relato(s))"
            log.info("API do app Zelo: %d relato(s) novo(s)", len(df_app))
        except (integracoes.FalhaIntegracao, ingestao.ArquivoInvalido) as e:
            integracoes_status["API do app Zelo"] = "não usada: lido o arquivo exportado (app_zelo_*.json)"
            log.warning("%s. Usando o arquivo exportado do app, se existir.", e)

        # 2) Leitura e validação (Pandas) --------------------------------------------
        res = ingestao.ingerir(cfg.pasta_entrada, run_id, df_app, mover_arquivos)
        contagens.update(lidos=res.lidos, quarentena=len(res.quarentena),
                         duplicados_no_lote=res.duplicados_no_lote)
        resumo_quarentena = res.quarentena.to_dict("records")
        banco.registrar_quarentena(run_id, resumo_quarentena)
        if res.arquivos_com_erro:
            alertas.append(f"{len(res.arquivos_com_erro)} arquivo(s) rejeitado(s) e movido(s) para entrada/com_erro")

        # 3) Idempotência: descarta o que já está no banco ------------------------------
        df = res.validos
        existentes = banco.chaves_existentes(df["chave"].tolist())
        contagens["ja_processados"] = len(existentes)
        if existentes:
            log.info("%d relato(s) já processado(s) antes foram ignorados (idempotência)", len(existentes))
        df = df[~df["chave"].isin(existentes)].reset_index(drop=True)

        # 4) IA: classificação de categoria ---------------------------------------------
        precisa_ia = df["canal"] != "app_zelo"
        predicoes = {}
        if precisa_ia.any():
            clf = Classificador.carregar_ou_treinar(cfg.caminho_modelo, cfg.caminho_treino)
            for idx, p in zip(df.index[precisa_ia], clf.prever(df.loc[precisa_ia, "descricao"].tolist())):
                predicoes[idx] = p

        # 5) Contexto de chuva por bairro (API Open-Meteo) ------------------------------
        clima = integracoes.ClimaOpenMeteo(cfg.clima_url, cfg.clima_timeout_s, cfg.clima_tentativas,
                                           cfg.espera_retry_s, cfg.clima_habilitado)
        chuva = {b: clima.chuva_hoje_mm(*coordenadas(b)) for b in df["bairro"].unique()}
        integracoes_status["Open-Meteo (chuva)"] = clima.status
        if clima.circuito_aberto:
            alertas.append("Open-Meteo indisponível: urgências calculadas sem o agravante de chuva")

        # 6) Decisão + gravação no banco --------------------------------------------------
        for idx, r in df.iterrows():
            try:
                if r["canal"] == "app_zelo":
                    categoria, conf, segunda, origem = r["categoria_informada"], None, "", "app Zelo (LLM + cidadão)"
                    urg_inf = r["urgencia_informada"]
                else:
                    p = predicoes[idx]
                    categoria, conf, segunda, origem = p.categoria, p.confianca, p.segunda_opcao, "NLP local"
                    urg_inf = None
                d = decidir(r["descricao"], r["bairro"], categoria, conf if conf is not None else 1.0,
                            chuva[r["bairro"]], cfg.limiar_confianca, cfg.limiar_chuva_forte_mm, urg_inf)
                dados = {
                    "protocolo": r["id_origem"] if r["canal"] == "app_zelo" else None,
                    "chave": r["chave"], "canal": r["canal"], "id_origem": r["id_origem"],
                    "recebido_em": pd.Timestamp(r["recebido_em"]).isoformat(timespec="minutes"),
                    "bairro": r["bairro"], "descricao": r["descricao"],
                    "dados_removidos": r["dados_removidos"], "categoria": categoria, "confianca": conf,
                    "origem_classificacao": origem, "urgencia": d.urgencia,
                    "justificativa": "; ".join(d.justificativa), "orgao": d.orgao,
                    "prazo_dias": PRAZO_DIAS[d.urgencia], "chuva_mm": chuva[r["bairro"]],
                    "status": "revisao_humana" if d.precisa_revisao else "encaminhado",
                    "motivos_revisao": "; ".join(d.motivos_revisao), "run_id": run_id,
                }
                protocolo = banco.inserir_solicitacao(dados, r["email_cidadao"] or None)
                if protocolo is None:
                    contagens["ja_processados"] += 1
                    continue
                linhas_novas.append({**dados, "protocolo": protocolo, "segunda_opcao": segunda,
                                     "descricao_anonimizada": dados["descricao"],
                                     "email": r["email_cidadao"] or None})
            except Exception as e:  # noqa: BLE001 - um relato com problema não derruba os outros
                log.exception("Falha ao processar %s/%s: %s", r["canal"], r["id_origem"], e)
                alertas.append(f"relato {r['canal']}/{r['id_origem']} não processado: {type(e).__name__}")

        contagens["novos"] = len(linhas_novas)
        revisao = [l for l in linhas_novas if l["status"] == "revisao_humana"]
        # Segurança acima de tudo: um caso CRÍTICO é despachado mesmo se também for para revisão.
        despachar = [l for l in linhas_novas if l["status"] == "encaminhado" or l["urgencia"] == "critica"]
        contagens["encaminhados"] = sum(1 for l in linhas_novas if l["status"] == "encaminhado")
        contagens["revisao_humana"] = len(revisao)
        contagens["com_dados_removidos"] = sum(1 for l in linhas_novas if l["dados_removidos"])
        log.info("%d nova(s) solicitação(ões): %d encaminhada(s), %d para revisão humana",
                 len(linhas_novas), contagens["encaminhados"], len(revisao))

        # 7) Planilhas ----------------------------------------------------------------------
        try:
            despachos = gerar_despachos(despachar, pasta_run / "despachos")
            arquivo_revisao = gerar_revisao(revisao, pasta_run)
            if not res.quarentena.empty:
                res.quarentena.to_csv(pasta_run / "quarentena.csv", index=False, encoding="utf-8-sig")
        except OSError as e:  # disco cheio, arquivo aberto no Excel etc.
            log.exception("Falha ao gravar planilhas: %s", e)
            alertas.append(f"planilhas não geradas: {e}")

        # 8) E-mails ---------------------------------------------------------------------
        carteiro.reenviar_pendentes()
        for l in linhas_novas:
            if not l["email"]:
                continue
            st = carteiro.enviar("cidadao", l["protocolo"], l["email"],
                                 f"Zelo | Protocolo {l['protocolo']} recebido", _corpo_cidadao(l))
            if st in ("enviado", "salvo_arquivo"):
                banco.apagar_contato(l["protocolo"])  # LGPD: e-mail não fica guardado
        for orgao, (arquivo, itens, criticos) in despachos.items():
            prefixo = "[CRÍTICO] " if criticos else ""
            carteiro.enviar("orgao", f"{run_id}:{orgao}", email_do_orgao(orgao),
                            f"{prefixo}Zelo | Despacho {run_id}: {itens} solicitação(ões)",
                            _corpo_orgao(orgao, itens, criticos, run_id), [arquivo])

    except Exception as e:  # noqa: BLE001
        status_final = "falhou"
        log.exception("Erro geral na execução: %s", e)
        alertas.append(f"execução interrompida: {type(e).__name__}: {e}")

    if status_final != "falhou" and (alertas or contagens["quarentena"]):
        status_final = "concluido_com_alertas"

    # 9) Relatório + e-mail para a coordenação -------------------------------------------
    resumo = {
        "run_id": run_id, "status": status_final, "inicio": inicio_iso,
        "fim": datetime.now().isoformat(timespec="seconds"),
        "duracao_s": time.monotonic() - inicio, "email_modo": cfg.email_modo,
        "contagens": {k: contagens.get(k, 0) for k in (
            "lidos", "quarentena", "duplicados_no_lote", "ja_processados", "novos",
            "encaminhados", "revisao_humana", "com_dados_removidos")},
        "integracoes": integracoes_status,
        "arquivos": {"ok": res.arquivos_ok if res else [], "com_erro": res.arquivos_com_erro if res else [],
                     "canais_sem_arquivo": res.canais_sem_arquivo if res else []},
        "por_urgencia": dict(Counter(l["urgencia"] for l in linhas_novas)),
        "por_orgao": {o: {"itens": i, "criticos": c} for o, (_, i, c) in despachos.items()},
        "revisao": [{"protocolo": l["protocolo"], "motivo": l["motivos_revisao"]} for l in revisao],
        "quarentena": resumo_quarentena,
        "emails": {},
        "alertas": alertas,
        "pasta_saida": str(pasta_run),
    }
    resumo["por_urgencia"] = {k: resumo["por_urgencia"][k] for k in ("critica", "alta", "media", "baixa")
                              if k in resumo["por_urgencia"]}
    relatorio = gerar_relatorio(resumo, pasta_run)
    try:
        anexos = [relatorio] + ([arquivo_revisao] if arquivo_revisao else [])
        carteiro.enviar("coordenacao", run_id, cfg.email_coordenacao,
                        f"Zelo | Relatório da execução {run_id} ({status_final})",
                        f"Execução {run_id} finalizada com status {status_final}.\n"
                        f"{contagens['novos']} nova(s) solicitação(ões), {len(revisao)} aguardando revisão humana.\n"
                        "Relatório completo e fila de revisão em anexo.\n", anexos)
    except Exception as e:  # noqa: BLE001
        log.exception("Não foi possível enviar o relatório: %s", e)
    resumo["emails"] = carteiro.contagem
    relatorio = gerar_relatorio(resumo, pasta_run)  # atualiza com o total de e-mails

    banco.finalizar_execucao(run_id, status_final, resumo)
    banco.fechar()
    log.info("===== Fim da execução %s: %s em %.1f s. Relatório: %s =====",
             run_id, status_final, resumo["duracao_s"], relatorio)
    return resumo
