"""Gera as evidências de validação em docs/evidencias/resultado_validacao.md.

Parte A: qualidade da IA no conjunto de teste ROTULADO À MÃO (72 relatos que
         não aparecem na base de treino).
Parte B: cenários de execução ponta a ponta, cada um numa pasta temporária,
         incluindo os casos de falha que o enunciado pede.

Uso: python -m scripts.validar
"""

from __future__ import annotations

import shutil
import tempfile
from email import message_from_string, policy
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from scripts.gerar_dados import gerar_lote_demo
from scripts.servidores_teste import HTTPLocal, SMTPLocal
from zelo_robo.classificador import Classificador
from zelo_robo.config import RAIZ, Config
from zelo_robo.regras import calcular_urgencia
from zelo_robo.robo import executar

SAIDA = RAIZ / "docs" / "evidencias"
CURTO = {
    "buraco_pavimentacao": "buraco", "iluminacao_publica": "ilum", "calcada_acessibilidade": "calcada",
    "alagamento_drenagem": "alag", "lixo_entulho": "lixo", "arvore_poda": "arvore",
    "sinalizacao_transito": "sinal", "outros": "outros",
}
ORDEM_URG = ["baixa", "media", "alta", "critica"]


# ---------------------------------------------------------------------------
# Parte A
# ---------------------------------------------------------------------------
def avaliar_ia(cfg: Config, arquivo: str, titulo: str, nota: str) -> list[str]:
    teste = pd.read_csv(RAIZ / "dados" / "teste" / arquivo)
    treino = pd.read_csv(cfg.caminho_treino)
    vazamento = set(teste["descricao"].str.lower()) & set(treino["descricao"].str.lower())

    clf = Classificador.carregar_ou_treinar(cfg.caminho_modelo, cfg.caminho_treino)
    pred = clf.prever(teste["descricao"].tolist())
    teste["pred"] = [p.categoria for p in pred]
    teste["conf"] = [p.confianca for p in pred]
    teste["urg_regra_cat_real"] = [calcular_urgencia(d, c, None)[0] for d, c in zip(teste["descricao"], teste["categoria"])]
    teste["urg_ponta_a_ponta"] = [calcular_urgencia(d, c, None)[0] for d, c in zip(teste["descricao"], teste["pred"])]
    teste["revisao"] = (teste["conf"] < cfg.limiar_confianca) | (teste["pred"] == "outros")

    n = len(teste)
    acc = accuracy_score(teste["categoria"], teste["pred"])
    f1 = f1_score(teste["categoria"], teste["pred"], average="macro")
    acertos = int((teste["categoria"] == teste["pred"]).sum())

    auto = teste[~teste["revisao"]]
    acc_auto = accuracy_score(auto["categoria"], auto["pred"]) if len(auto) else 0
    rev = teste[teste["revisao"]]
    erros_pegos = int(((rev["categoria"] != rev["pred"])).sum())
    erros_total = n - acertos

    def dist(a, b):
        return abs(ORDEM_URG.index(a) - ORDEM_URG.index(b))

    urg_ok = int((teste["urgencia"] == teste["urg_regra_cat_real"]).sum())
    urg_tol = int(sum(dist(a, b) <= 1 for a, b in zip(teste["urgencia"], teste["urg_regra_cat_real"])))
    subestimou = int(sum(ORDEM_URG.index(p) < ORDEM_URG.index(r)
                         for r, p in zip(teste["urgencia"], teste["urg_regra_cat_real"])))
    crit = teste[teste["urgencia"] == "critica"]
    crit_ok = int((crit["urg_regra_cat_real"] == "critica").sum())
    falso_crit = int(((teste["urg_regra_cat_real"] == "critica") & (teste["urgencia"] != "critica")).sum())

    por_cat = teste["categoria"].value_counts().iloc[0]
    md = [
        f"## {titulo}",
        "",
        nota,
        "",
        f"- Amostra: **{n} relatos** escritos à mão, {por_cat} por categoria, com categoria e urgência esperadas "
        f"(`dados/teste/{arquivo}`).",
        f"- Base de treino: {len(treino)} relatos sintéticos gerados por `scripts/gerar_dados.py`. "
        f"Frases idênticas entre treino e teste: **{len(vazamento)}**.",
        f"- Limiar de confiança para revisão humana: {cfg.limiar_confianca:.0%}.",
        "",
        "### Categoria (modelo de NLP)",
        "",
        "| Métrica | Resultado |",
        "|---|---|",
        f"| Acurácia | **{acc:.1%}** ({acertos}/{n}) |",
        f"| F1 macro | {f1:.3f} |",
        f"| Relatos enviados para revisão humana | {len(rev)} ({len(rev)/n:.0%}) |",
        f"| Acurácia nos decididos automaticamente | **{acc_auto:.1%}** ({int((auto['categoria']==auto['pred']).sum())}/{len(auto)}) |",
        f"| Erros de categoria que caíram na revisão humana | {erros_pegos} de {erros_total} |",
        "",
        "Relatório por classe:",
        "",
        "```",
        classification_report(teste["categoria"], teste["pred"], zero_division=0),
        "```",
        "",
        "Matriz de confusão (linha = real, coluna = previsto):",
        "",
    ]
    rotulos = list(CURTO)
    cm = confusion_matrix(teste["categoria"], teste["pred"], labels=rotulos)
    md.append("| real \\ previsto | " + " | ".join(CURTO[r] for r in rotulos) + " |")
    md.append("|---" * (len(rotulos) + 1) + "|")
    for r, linha in zip(rotulos, cm):
        md.append(f"| **{CURTO[r]}** | " + " | ".join(f"**{v}**" if i == rotulos.index(r) else (str(v) if v else "·")
                                                    for i, v in enumerate(linha)) + " |")

    md += [
        "",
        "### Urgência (regras explicáveis)",
        "",
        "| Métrica | Resultado |",
        "|---|---|",
        f"| Acerto exato (usando a categoria real) | **{urg_ok/n:.1%}** ({urg_ok}/{n}) |",
        f"| Acerto com tolerância de 1 nível | {urg_tol/n:.1%} ({urg_tol}/{n}) |",
        f"| Acerto exato ponta a ponta (categoria prevista pela IA) | "
        f"{(teste['urgencia']==teste['urg_ponta_a_ponta']).mean():.1%} |",
        f"| Casos CRÍTICOS identificados como críticos | **{crit_ok}/{len(crit)}** |",
        f"| Falsos críticos (marcado crítico sem ser) | {falso_crit} |",
        f"| Urgência subestimada (abaixo do esperado) | {subestimou} |",
        "",
        "### Todos os erros (para análise)",
        "",
        "| Id | Relato | Esperado | Previsto | Conf. | Revisão? |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in teste[teste["categoria"] != teste["pred"]].iterrows():
        md.append(f"| {r['id']} | {r['descricao'][:80]} | {CURTO[r['categoria']]} | {CURTO[r['pred']]} | "
                  f"{r['conf']:.0%} | {'sim' if r['revisao'] else 'não'} |")
    md += ["", "| Id | Relato | Urgência esperada | Regra deu |", "|---|---|---|---|"]
    for _, r in teste[teste["urgencia"] != teste["urg_regra_cat_real"]].iterrows():
        md.append(f"| {r['id']} | {r['descricao'][:80]} | {r['urgencia']} | {r['urg_regra_cat_real']} |")

    SAIDA.mkdir(parents=True, exist_ok=True)
    teste.to_csv(SAIDA / f"predicoes_{arquivo}", index=False)
    return md


# ---------------------------------------------------------------------------
# Parte B
# ---------------------------------------------------------------------------
def cfg_temporaria(base: Path, **extra) -> Config:
    cfg = Config.carregar()
    cfg.pasta_entrada = base / "entrada"
    cfg.pasta_saida = base / "saida"
    cfg.pasta_logs = base / "logs"
    cfg.caminho_banco = base / "zelo_robo.db"
    cfg.zelo_api_url, cfg.zelo_gestor_token = "", ""
    cfg.email_modo = "arquivo"
    cfg.clima_habilitado = False
    cfg.espera_retry_s = 0.05
    cfg.nivel_log_console = 100  # silencia o terminal; o log completo fica no arquivo
    for k, v in extra.items():
        setattr(cfg, k, v)
    return cfg


def trecho_log(cfg: Config, *termos: str, limite: int = 6) -> list[str]:
    linhas = (cfg.pasta_logs / "robo.log").read_text(encoding="utf-8").splitlines()
    sel = [l for l in linhas if any(t in l for t in termos)]
    return ["```"] + [l[:200] for l in sel[-limite:]] + ["```"]


def cenarios() -> list[str]:
    md = ["## Parte B: execução ponta a ponta e casos de falha", ""]
    tabela = ["| # | Cenário | O que foi feito | Resultado observado | OK? |", "|---|---|---|---|---|"]
    detalhes: list[str] = []
    base_tmp = Path(tempfile.mkdtemp(prefix="zelo_validacao_"))

    def registrar(n, nome, feito, obs, ok, log_linhas=None):
        tabela.append(f"| {n} | {nome} | {feito} | {obs} | {'✅' if ok else '❌'} |")
        if log_linhas:
            detalhes.extend([f"**Cenário {n}: {nome}** (trecho do log)", ""] + log_linhas + [""])

    # 1 e 2: execução normal + reexecução (idempotência)
    b = base_tmp / "c1"
    cfg = cfg_temporaria(b)
    gerar_lote_demo(cfg.pasta_entrada)
    r1 = executar(cfg)
    c = r1["contagens"]
    registrar(1, "Execução normal (lote de demonstração)", "3 canais, 22 linhas com erros propositais",
              f"{c['novos']} novos, {c['quarentena']} em quarentena, {c['duplicados_no_lote']} duplicado, "
              f"{c['revisao_humana']} para revisão, {c['com_dados_removidos']} com CPF/telefone removido, "
              f"{sum(r1['emails'].values())} e-mails gerados",
              c["novos"] == 16 and c["quarentena"] == 5 and c["duplicados_no_lote"] == 1 and r1["status"] != "falhou",
              trecho_log(cfg, "Quarentena", "duplicado", "nova(s)"))
    gerar_lote_demo(cfg.pasta_entrada)  # mesmo lote chegando de novo
    r2 = executar(cfg)
    c2 = r2["contagens"]
    registrar(2, "Idempotência: o mesmo lote chega de novo", "reprocessar os mesmos arquivos",
              f"{c2['novos']} novos, {c2['ja_processados']} já processados ignorados, "
              f"{r2['emails']['salvo_arquivo'] - 1} e-mail repetido (só o relatório da nova execução)",
              c2["novos"] == 0 and c2["ja_processados"] == 16 and r2["emails"]["salvo_arquivo"] == 1,
              trecho_log(cfg, "idempotência"))

    # 3: arquivos corrompidos / colunas faltando
    b = base_tmp / "c3"
    cfg = cfg_temporaria(b)
    gerar_lote_demo(cfg.pasta_entrada)
    (cfg.pasta_entrada / "subprefeitura_corrompida.xlsx").write_bytes(b"isto nao e um excel")
    (cfg.pasta_entrada / "sp156_sem_colunas.csv").write_text("A;B\n1;2\n", encoding="utf-8")
    r = executar(cfg)
    movidos = sorted(p.name.split("__", 1)[1] for p in (cfg.pasta_entrada / "com_erro").iterdir())
    registrar(3, "Arquivo corrompido e arquivo sem as colunas esperadas",
              "Excel inválido + CSV com colunas erradas junto com o lote bom",
              f"rejeitados {r['arquivos']['com_erro']}, movidos para entrada/com_erro; "
              f"os outros arquivos geraram {r['contagens']['novos']} protocolos",
              set(r["arquivos"]["com_erro"]) == {"subprefeitura_corrompida.xlsx", "sp156_sem_colunas.csv"}
              and r["contagens"]["novos"] == 16 and len(movidos) == 2,
              trecho_log(cfg, "rejeitado"))

    # 4: pasta de entrada vazia (canal sem arquivo)
    b = base_tmp / "c4"
    cfg = cfg_temporaria(b)
    r = executar(cfg)
    registrar(4, "Nenhum arquivo na entrada", "rodar o robô com a pasta vazia",
              f"status '{r['status']}', avisos para {len(r['arquivos']['canais_sem_arquivo'])} canais, relatório gerado",
              r["status"] != "falhou" and len(r["arquivos"]["canais_sem_arquivo"]) == 3,
              trecho_log(cfg, "sem arquivo", limite=3))

    # 5: APIs fora do ar
    b = base_tmp / "c5"
    cfg = cfg_temporaria(b, clima_habilitado=True, clima_url="http://127.0.0.1:9/indisponivel",
                         clima_timeout_s=1, zelo_api_url="http://127.0.0.1:9", zelo_gestor_token="token-teste-1234567",
                         zelo_api_timeout_s=1)
    gerar_lote_demo(cfg.pasta_entrada)
    r = executar(cfg)
    registrar(5, "API do app Zelo e Open-Meteo fora do ar", "endereços que recusam conexão",
              f"app: {r['integracoes']['API do app Zelo']}; chuva: {r['integracoes']['Open-Meteo (chuva)']}; "
              f"{r['contagens']['novos']} protocolos gerados mesmo assim",
              r["contagens"]["novos"] == 16 and "indisponível" in r["integracoes"]["Open-Meteo (chuva)"],
              trecho_log(cfg, "tentativa", "indisponível", "não configurada", limite=8))

    # 6: retry funcionando + chuva forte elevando urgência
    http = HTTPLocal(porta=8765, chuva_mm=35.0, falhas_iniciais=2).iniciar()
    try:
        b = base_tmp / "c6"
        cfg = cfg_temporaria(b, clima_habilitado=True, clima_url="http://127.0.0.1:8765/v1/forecast")
        gerar_lote_demo(cfg.pasta_entrada)
        r = executar(cfg)
        import sqlite3
        con = sqlite3.connect(cfg.caminho_banco)
        elevados = con.execute("SELECT COUNT(*) FROM solicitacoes WHERE justificativa LIKE '%mm de chuva%'").fetchone()[0]
        con.close()
    finally:
        http.parar()
    registrar(6, "Open-Meteo instável (2 respostas HTTP 503) e depois 35 mm de chuva",
              "servidor local imitando a API",
              f"retry com espera recuperou a resposta ({http.chamadas} chamadas); "
              f"{elevados} alagamento(s)/árvore(s) com urgência elevada pela chuva",
              r["integracoes"]["Open-Meteo (chuva)"].startswith("ok") and elevados >= 1,
              trecho_log(cfg, "Open-Meteo", limite=3))

    # 7 e 8: SMTP fora do ar -> pendente -> reenvio quando volta
    b = base_tmp / "c7"
    cfg = cfg_temporaria(b, email_modo="smtp", smtp_host="127.0.0.1", smtp_porta=2526, smtp_tls=False,
                         smtp_timeout_s=2)
    gerar_lote_demo(cfg.pasta_entrada)
    r = executar(cfg)
    pend = r["emails"]["pendente"]
    registrar(7, "Servidor de e-mail fora do ar", "SMTP em porta sem servidor",
              f"{pend} e-mails ficaram 'pendente' com o .eml guardado; a execução terminou normalmente",
              pend == 17 and r["status"] != "falhou", trecho_log(cfg, "SMTP falhou", limite=3))
    smtp = SMTPLocal(porta=2526).iniciar()
    try:
        r = executar(cfg)  # entrada vazia: só reenvia os pendentes
        recebidos = [message_from_string(m, policy=policy.default)["Subject"] for m in smtp.mensagens]
    finally:
        smtp.parar()
    registrar(8, "Servidor de e-mail volta na execução seguinte", "SMTP local de teste ligado",
              f"{len(recebidos)} mensagens entregues (17 pendentes + relatório novo), sem duplicar",
              len(recebidos) == 18, trecho_log(cfg, "reenviado", limite=2))
    detalhes += ["**Cenário 8: assuntos recebidos pelo SMTP local (amostra)**", ""] + \
                [f"- {s}" for s in recebidos[:4]] + [f"- ... e mais {len(recebidos) - 4}", ""]

    # 9: modelo apagado / corrompido
    b = base_tmp / "c9"
    modelo_tmp = b / "modelo" / "classificador.joblib"
    modelo_tmp.parent.mkdir(parents=True)
    modelo_tmp.write_bytes(b"arquivo corrompido")
    cfg = cfg_temporaria(b, caminho_modelo=modelo_tmp)
    gerar_lote_demo(cfg.pasta_entrada)
    r = executar(cfg)
    registrar(9, "Arquivo do modelo de IA corrompido", "substituir o .joblib por lixo",
              f"robô detectou, retreinou e seguiu ({r['contagens']['novos']} protocolos)",
              r["contagens"]["novos"] == 16, trecho_log(cfg, "Modelo", limite=2))

    # 10: LGPD no log
    log_txt = (base_tmp / "c1" / "logs" / "robo.log").read_text(encoding="utf-8")
    vazou = any(x in log_txt for x in ("123.456.789-00", "98765-4321", "maria.silva@example.com"))
    registrar(10, "Dados pessoais no log", "procurar CPF, telefone e e-mail do lote no robo.log",
              "nenhum dado pessoal encontrado no log" if not vazou else "dado pessoal encontrado",
              not vazou)

    shutil.rmtree(base_tmp, ignore_errors=True)
    return md + tabela + ["", "### Trechos de log dos cenários", ""] + detalhes


def main() -> None:
    cfg = Config.carregar()
    print("Parte A: avaliando a IA no conjunto de teste...")
    md = ["# Resultado da validação (gerado por `python -m scripts.validar`)", ""]
    md += avaliar_ia(
        cfg, "casos_teste_rotulados.csv", "Parte A: qualidade da IA no conjunto de TESTE (resultado oficial)",
        "Conjunto escrito depois que as regras e o modelo foram finalizados. Nada foi ajustado olhando para ele.") + [""]
    md += avaliar_ia(
        cfg, "casos_desenvolvimento.csv", "Anexo: conjunto de DESENVOLVIMENTO (usado para ajustar as regras)",
        "Na primeira versão (regras v1) este conjunto deu: categoria 93,1%, urgência exata 61,1% e só 5 de 8 "
        "casos críticos detectados. Os erros motivaram as regras v2. Como as regras foram ajustadas aqui, "
        "os números abaixo são otimistas; o resultado que vale é o da Parte A.") + [""]
    print("Parte B: rodando 10 cenários ponta a ponta (leva cerca de 1 minuto)...")
    md += cenarios()
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "resultado_validacao.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Evidências escritas em {SAIDA / 'resultado_validacao.md'}")


if __name__ == "__main__":
    main()
