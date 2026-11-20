"""Persistência em SQLite (biblioteca padrão do Python).

Para uma POC, SQLite é suficiente e não exige servidor. Em produção, a mesma
interface poderia ser implementada sobre PostgreSQL sem mudar routers/pipelines.
"""

import json
import random
import secrets
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.erros import ErroConflito, ErroNaoEncontrado
from app.providers.bairros import BAIRROS, coordenadas_mapa
from app.schemas.relato import Categoria, Status, Urgencia

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analises (
    id TEXT PRIMARY KEY,
    criado_em TEXT NOT NULL,
    entrada_json TEXT NOT NULL,
    analise_json TEXT NOT NULL,
    confirmada INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS relatos (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo TEXT UNIQUE,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    bairro TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    categoria TEXT NOT NULL,
    urgencia TEXT NOT NULL,
    categoria_ia TEXT NOT NULL,
    urgencia_ia TEXT NOT NULL,
    confianca_ia REAL NOT NULL,
    status TEXT NOT NULL,
    resumo TEXT NOT NULL,
    orgao_responsavel TEXT NOT NULL,
    prazo_estimado_dias INTEGER NOT NULL,
    descricao_anonimizada TEXT NOT NULL,
    ia_corrigida INTEGER NOT NULL,
    feedback TEXT,
    feedback_comentario TEXT,
    nota_gestor TEXT,
    analise_id TEXT,
    simulado INTEGER NOT NULL DEFAULT 0
);
"""


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repositorio:
    def __init__(self, caminho: str):
        self._caminho = caminho
        self._trava = threading.Lock()
        if caminho != ":memory:":
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self._conexao = sqlite3.connect(caminho, check_same_thread=False)
        self._conexao.row_factory = sqlite3.Row
        self._conexao.executescript(_SCHEMA)
        self._migrar()

    def _migrar(self) -> None:
        """Bancos criados antes da coluna analise_id recebem a coluna nova."""
        colunas = {l["name"] for l in self._conexao.execute("PRAGMA table_info(relatos)")}
        if "analise_id" not in colunas:
            self._conexao.execute("ALTER TABLE relatos ADD COLUMN analise_id TEXT")
            self._conexao.commit()

    @contextmanager
    def _tx(self):
        with self._trava:
            try:
                yield self._conexao
                self._conexao.commit()
            except Exception:
                self._conexao.rollback()
                raise

    # ----------------------------------------------------------------- análises
    def salvar_analise(self, entrada: dict, analise: dict) -> str:
        analise_id = uuid.uuid4().hex
        with self._tx() as c:
            c.execute(
                "INSERT INTO analises (id, criado_em, entrada_json, analise_json) VALUES (?,?,?,?)",
                (analise_id, _agora(), json.dumps(entrada, ensure_ascii=False), json.dumps(analise, ensure_ascii=False)),
            )
        return analise_id

    def obter_analise(self, analise_id: str) -> tuple[dict, dict, bool]:
        linha = self._conexao.execute("SELECT * FROM analises WHERE id = ?", (analise_id,)).fetchone()
        if not linha:
            raise ErroNaoEncontrado("Essa análise expirou ou não existe. Envie o relato novamente.")
        return json.loads(linha["entrada_json"]), json.loads(linha["analise_json"]), bool(linha["confirmada"])

    # ------------------------------------------------------------------ relatos
    def criar_relato(self, analise_id: str, dados: dict) -> dict:
        # coordenadas definitivas dependem do protocolo (gerado pelo AUTOINCREMENT)
        dados = {**dados, "latitude": 0.0, "longitude": 0.0, "analise_id": analise_id}
        with self._tx() as c:
            atualizou = c.execute(
                "UPDATE analises SET confirmada = 1 WHERE id = ? AND confirmada = 0", (analise_id,)
            ).rowcount
            if not atualizou:
                raise ErroConflito()
            colunas = ", ".join(dados)
            marcadores = ", ".join("?" for _ in dados)
            cur = c.execute(f"INSERT INTO relatos ({colunas}) VALUES ({marcadores})", tuple(dados.values()))
            protocolo = f"ZL-{datetime.now().year}-{cur.lastrowid:06d}"
            lat, lon = coordenadas_mapa(dados["bairro"], protocolo)
            c.execute(
                "UPDATE relatos SET protocolo = ?, latitude = ?, longitude = ? WHERE seq = ?",
                (protocolo, lat, lon, cur.lastrowid),
            )
        return self.obter_relato(protocolo)

    def obter_relato(self, protocolo: str) -> dict:
        linha = self._conexao.execute("SELECT * FROM relatos WHERE protocolo = ?", (protocolo,)).fetchone()
        if not linha:
            raise ErroNaoEncontrado("Protocolo não encontrado.")
        return dict(linha)

    def listar_relatos(
        self,
        categoria: str | None = None,
        urgencia: str | None = None,
        bairro: str | None = None,
        status: str | None = None,
        dias: int | None = None,
        incluir_simulados: bool = True,
    ) -> list[dict]:
        sql, params = "SELECT * FROM relatos WHERE protocolo IS NOT NULL", []
        for coluna, valor in (("categoria", categoria), ("urgencia", urgencia), ("bairro", bairro), ("status", status)):
            if valor:
                sql += f" AND {coluna} = ?"
                params.append(valor)
        if dias:
            sql += " AND criado_em >= ?"
            params.append((datetime.now(timezone.utc) - timedelta(days=dias)).isoformat())
        if not incluir_simulados:
            sql += " AND simulado = 0"
        sql += " ORDER BY criado_em DESC LIMIT 1000"
        return [dict(l) for l in self._conexao.execute(sql, params).fetchall()]

    def registrar_feedback(self, protocolo: str, analise_id: str, avaliacao: str, comentario: str | None) -> dict:
        with self._tx() as c:
            linha = c.execute("SELECT analise_id, feedback FROM relatos WHERE protocolo = ?", (protocolo,)).fetchone()
            # Mesma resposta para "não existe" e "não é seu": não revela protocolos alheios.
            if not linha or not linha["analise_id"] or not secrets.compare_digest(linha["analise_id"], analise_id):
                raise ErroNaoEncontrado("Protocolo não encontrado.")
            if linha["feedback"]:
                raise ErroConflito("Você já avaliou este relato. Obrigado!")
            c.execute(
                "UPDATE relatos SET feedback = ?, feedback_comentario = ?, atualizado_em = ? WHERE protocolo = ?",
                (avaliacao, comentario, _agora(), protocolo),
            )
        return self.obter_relato(protocolo)

    def atualizar_status(self, protocolo: str, status: str, nota: str | None) -> dict:
        with self._tx() as c:
            n = c.execute(
                "UPDATE relatos SET status = ?, nota_gestor = COALESCE(?, nota_gestor), atualizado_em = ? WHERE protocolo = ?",
                (status, nota, _agora(), protocolo),
            ).rowcount
        if not n:
            raise ErroNaoEncontrado("Protocolo não encontrado.")
        return self.obter_relato(protocolo)

    # ------------------------------------------------------- dados simulados
    def popular_demo(self, quantidade: int = 60) -> None:
        """Gera relatos SIMULADOS (simulado=1) para o painel não começar vazio.
        Eles aparecem identificados na interface e podem ser ocultados no filtro."""
        if self._conexao.execute("SELECT COUNT(*) FROM relatos").fetchone()[0]:
            return
        rnd = random.Random(42)
        resumos = {
            Categoria.BURACO: "Buraco na pista dificultando a passagem de veículos",
            Categoria.ILUMINACAO: "Poste com lâmpada apagada deixando a rua escura",
            Categoria.CALCADA: "Calçada quebrada impedindo passagem de cadeirantes",
            Categoria.ALAGAMENTO: "Boca de lobo entupida causando alagamento",
            Categoria.LIXO: "Descarte irregular de entulho na via pública",
            Categoria.ARVORE: "Galho de árvore apoiado na rede elétrica",
            Categoria.SINALIZACAO: "Semáforo apagado em cruzamento movimentado",
        }
        from app.pipelines.regras import ORGAOS, PRAZOS  # import tardio evita ciclo

        agora = datetime.now(timezone.utc)
        bairros = list(BAIRROS)
        pesos_urg = [0.25, 0.4, 0.25, 0.1]
        with self._tx() as c:
            for i in range(quantidade):
                cat = rnd.choice(list(resumos))
                urg = rnd.choices(list(Urgencia), weights=pesos_urg)[0]
                corrigida = rnd.random() < 0.15
                criado = agora - timedelta(days=rnd.uniform(0, 29), hours=rnd.uniform(0, 23))
                idade = (agora - criado).days
                status = rnd.choice(
                    [Status.RESOLVIDO, Status.ENCAMINHADO] if idade > 10 else [Status.RECEBIDO, Status.EM_ANALISE, Status.ENCAMINHADO]
                )
                bairro = rnd.choice(bairros)
                protocolo = f"ZL-SIM-{i + 1:04d}"
                lat, lon = coordenadas_mapa(bairro, protocolo)
                c.execute(
                    """INSERT INTO relatos (protocolo, criado_em, atualizado_em, bairro, latitude, longitude,
                    categoria, urgencia, categoria_ia, urgencia_ia, confianca_ia, status, resumo,
                    orgao_responsavel, prazo_estimado_dias, descricao_anonimizada, ia_corrigida,
                    feedback, simulado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (
                        protocolo, criado.isoformat(), criado.isoformat(), bairro, lat, lon,
                        cat.value, urg.value, cat.value,
                        (Urgencia.de_nivel(urg.nivel - 1) if corrigida else urg).value,
                        round(rnd.uniform(0.6, 0.98), 2), status.value, resumos[cat],
                        ORGAOS[cat], PRAZOS[urg], "[relato simulado para demonstração]", int(corrigida),
                        rnd.choices([None, "util", "incorreto"], weights=[0.5, 0.42, 0.08])[0],
                    ),
                )
