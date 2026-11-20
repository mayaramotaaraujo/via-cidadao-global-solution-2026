"""TEMA 3: banco de dados SQL (SQLite).

O banco é o que torna o robô IDEMPOTENTE: cada relato tem uma `chave` única
(hash de canal + id de origem). Rodar o robô duas vezes com o mesmo arquivo
não duplica protocolos nem reenvia e-mails.

Separação por privacidade: o e-mail do cidadão fica numa tabela própria
(`contatos`) e é APAGADO assim que a confirmação é enviada. O banco não guarda
o texto original, só o texto já anonimizado.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

ESQUEMA = """
CREATE TABLE IF NOT EXISTS execucoes (
    run_id      TEXT PRIMARY KEY,
    inicio      TEXT NOT NULL,
    fim         TEXT,
    status      TEXT NOT NULL,
    resumo_json TEXT
);

CREATE TABLE IF NOT EXISTS solicitacoes (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo            TEXT UNIQUE,
    chave                TEXT NOT NULL UNIQUE,
    canal                TEXT NOT NULL,
    id_origem            TEXT NOT NULL,
    recebido_em          TEXT NOT NULL,
    bairro               TEXT NOT NULL,
    descricao_anonimizada TEXT NOT NULL,
    dados_removidos      TEXT,
    categoria            TEXT NOT NULL,
    confianca            REAL,
    origem_classificacao TEXT NOT NULL,
    urgencia             TEXT NOT NULL CHECK (urgencia IN ('baixa','media','alta','critica')),
    justificativa        TEXT,
    orgao                TEXT NOT NULL,
    prazo_dias           INTEGER NOT NULL,
    chuva_mm             REAL,
    status               TEXT NOT NULL CHECK (status IN ('encaminhado','revisao_humana')),
    motivos_revisao      TEXT,
    run_id               TEXT NOT NULL REFERENCES execucoes(run_id),
    criado_em            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_solic_run ON solicitacoes(run_id);

CREATE TABLE IF NOT EXISTS contatos (
    protocolo TEXT PRIMARY KEY REFERENCES solicitacoes(protocolo),
    email     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS envios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo          TEXT NOT NULL,
    referencia    TEXT NOT NULL,
    destinatario  TEXT NOT NULL,
    assunto       TEXT NOT NULL,
    status        TEXT NOT NULL,
    tentativas    INTEGER NOT NULL DEFAULT 0,
    arquivo_eml   TEXT,
    erro          TEXT,
    run_id        TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    UNIQUE (tipo, referencia)
);

CREATE TABLE IF NOT EXISTS quarentena (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL,
    canal            TEXT,
    id_origem        TEXT,
    bairro_informado TEXT,
    motivo           TEXT NOT NULL
);
"""


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Banco:
    def __init__(self, caminho: Path):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(caminho, timeout=10)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA)

    def fechar(self) -> None:
        self.con.close()

    @contextmanager
    def transacao(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.con
            self.con.commit()
        except Exception:
            self.con.rollback()
            raise

    # -- execuções -----------------------------------------------------------
    def iniciar_execucao(self, run_id: str) -> None:
        with self.transacao() as c:
            c.execute("INSERT INTO execucoes (run_id, inicio, status) VALUES (?, ?, 'rodando')",
                      (run_id, agora()))

    def finalizar_execucao(self, run_id: str, status: str, resumo: dict) -> None:
        with self.transacao() as c:
            c.execute("UPDATE execucoes SET fim = ?, status = ?, resumo_json = ? WHERE run_id = ?",
                      (agora(), status, json.dumps(resumo, ensure_ascii=False, default=str), run_id))

    # -- solicitações --------------------------------------------------------
    def chaves_existentes(self, chaves: list[str]) -> set[str]:
        if not chaves:
            return set()
        marcadores = ",".join("?" * len(chaves))
        linhas = self.con.execute(f"SELECT chave FROM solicitacoes WHERE chave IN ({marcadores})", chaves)
        return {r["chave"] for r in linhas}

    def inserir_solicitacao(self, dados: dict, email: str | None) -> str | None:
        """Insere e devolve o protocolo. Devolve None se a chave já existia (idempotência)."""
        with self.transacao() as c:
            try:
                cur = c.execute(
                    """INSERT INTO solicitacoes
                       (protocolo, chave, canal, id_origem, recebido_em, bairro, descricao_anonimizada,
                        dados_removidos, categoria, confianca, origem_classificacao, urgencia,
                        justificativa, orgao, prazo_dias, chuva_mm, status, motivos_revisao, run_id, criado_em)
                       VALUES (:protocolo, :chave, :canal, :id_origem, :recebido_em, :bairro, :descricao,
                        :dados_removidos, :categoria, :confianca, :origem_classificacao, :urgencia,
                        :justificativa, :orgao, :prazo_dias, :chuva_mm, :status, :motivos_revisao, :run_id, :criado_em)""",
                    {**dados, "protocolo": dados.get("protocolo"), "criado_em": agora()},
                )
            except sqlite3.IntegrityError as e:
                if "solicitacoes.chave" in str(e) or "solicitacoes.protocolo" in str(e):
                    return None  # já processado em outra execução
                raise
            protocolo = dados.get("protocolo")
            if not protocolo:
                ano = dados["recebido_em"][:4]
                protocolo = f"ZR-{ano}-{cur.lastrowid:06d}"
                c.execute("UPDATE solicitacoes SET protocolo = ? WHERE id = ?", (protocolo, cur.lastrowid))
            if email:
                c.execute("INSERT OR REPLACE INTO contatos (protocolo, email) VALUES (?, ?)", (protocolo, email))
            return protocolo

    def solicitacoes_da_execucao(self, run_id: str) -> list[sqlite3.Row]:
        return list(self.con.execute(
            "SELECT * FROM solicitacoes WHERE run_id = ? ORDER BY "
            "CASE urgencia WHEN 'critica' THEN 0 WHEN 'alta' THEN 1 WHEN 'media' THEN 2 ELSE 3 END, recebido_em",
            (run_id,)))

    def email_do_protocolo(self, protocolo: str) -> str | None:
        r = self.con.execute("SELECT email FROM contatos WHERE protocolo = ?", (protocolo,)).fetchone()
        return r["email"] if r else None

    def apagar_contato(self, protocolo: str) -> None:
        with self.transacao() as c:
            c.execute("DELETE FROM contatos WHERE protocolo = ?", (protocolo,))

    # -- envios --------------------------------------------------------------
    def envio(self, tipo: str, referencia: str) -> sqlite3.Row | None:
        return self.con.execute("SELECT * FROM envios WHERE tipo = ? AND referencia = ?",
                                (tipo, referencia)).fetchone()

    def registrar_envio(self, tipo: str, referencia: str, destinatario: str, assunto: str,
                        status: str, tentativas: int, run_id: str, arquivo_eml: str | None = None,
                        erro: str | None = None) -> None:
        with self.transacao() as c:
            c.execute(
                """INSERT INTO envios (tipo, referencia, destinatario, assunto, status, tentativas,
                                       arquivo_eml, erro, run_id, atualizado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (tipo, referencia) DO UPDATE SET
                     status = excluded.status, tentativas = envios.tentativas + excluded.tentativas,
                     arquivo_eml = excluded.arquivo_eml, erro = excluded.erro,
                     run_id = excluded.run_id, atualizado_em = excluded.atualizado_em""",
                (tipo, referencia, destinatario, assunto, status, tentativas, arquivo_eml, erro, run_id, agora()))

    def envios_pendentes(self) -> list[sqlite3.Row]:
        return list(self.con.execute("SELECT * FROM envios WHERE status = 'pendente' ORDER BY id"))

    # -- quarentena ----------------------------------------------------------
    def registrar_quarentena(self, run_id: str, linhas: list[dict]) -> None:
        if not linhas:
            return
        with self.transacao() as c:
            c.executemany(
                "INSERT INTO quarentena (run_id, canal, id_origem, bairro_informado, motivo) "
                "VALUES (:run_id, :canal, :id_origem, :bairro_informado, :motivo)",
                [{**l, "run_id": run_id} for l in linhas])
