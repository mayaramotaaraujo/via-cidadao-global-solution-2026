"""TEMA 1: tratamento de arquivos e dados com Pandas.

Cada canal manda os relatos num formato diferente:

| Canal           | Arquivo                 | Formato                                  |
|-----------------|-------------------------|------------------------------------------|
| SP156           | sp156_*.csv             | CSV com ';', datas dd/mm/aaaa, caixa alta |
| Subprefeitura   | subprefeitura_*.xlsx    | Excel preenchido à mão, "Sim"/"Não"      |
| App Zelo        | API REST ou app_zelo_*.json | JSON já triado pelo app              |

Este módulo lê tudo, padroniza num único DataFrame, valida linha a linha e manda
o que não presta para a quarentena (com o motivo), sem parar o robô.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .privacidade import anonimizar, email_valido, hash_curto, mascarar_email
from .referencia import CATEGORIAS, URGENCIAS, normalizar_bairro

log = logging.getLogger("zelo.ingestao")

COLUNAS = [
    "chave", "canal", "id_origem", "recebido_em", "bairro", "descricao",
    "dados_removidos", "email_cidadao", "categoria_informada", "urgencia_informada",
]

# Mapeamento "nome da coluna no arquivo" -> nome padronizado
_MAPA_SP156 = {
    "NUM_SOLICITACAO": "id_origem",
    "DATA_ABERTURA": "recebido_em",
    "DISTRITO": "bairro",
    "DESCRICAO_SOLICITACAO": "descricao",
    "EMAIL_CONTATO": "email_cidadao",
    "ACEITE_CONTATO": "consentimento",
}
_MAPA_SUBPREF = {
    "Nº": "id_origem",
    "Data": "recebido_em",
    "Bairro": "bairro",
    "Relato do munícipe": "descricao",
    "E-mail": "email_cidadao",
    "Autoriza contato?": "consentimento",
}
_MAPA_APP = {
    "protocolo": "id_origem",
    "criado_em": "recebido_em",
    "bairro": "bairro",
    "descricao_anonimizada": "descricao",
    "categoria": "categoria_informada",
    "urgencia": "urgencia_informada",
}

TAMANHO_MINIMO_DESCRICAO = 15


class ArquivoInvalido(Exception):
    """O arquivo inteiro não pôde ser lido (corrompido, colunas faltando...)."""


@dataclass
class ResultadoIngestao:
    validos: pd.DataFrame
    quarentena: pd.DataFrame
    arquivos_ok: list[str] = field(default_factory=list)
    arquivos_com_erro: list[str] = field(default_factory=list)
    canais_sem_arquivo: list[str] = field(default_factory=list)
    lidos: int = 0
    duplicados_no_lote: int = 0


# ---------------------------------------------------------------------------
# Leitura por canal
# ---------------------------------------------------------------------------
def _renomear(df: pd.DataFrame, mapa: dict[str, str], origem: str) -> pd.DataFrame:
    df = df.rename(columns=lambda c: str(c).strip())
    faltando = [c for c in mapa if c not in df.columns]
    if faltando:
        raise ArquivoInvalido(f"{origem}: colunas obrigatórias ausentes {faltando}")
    return df[list(mapa)].rename(columns=mapa)


def ler_sp156(caminho: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8", keep_default_na=False)
    except UnicodeDecodeError:
        df = pd.read_csv(caminho, sep=";", dtype=str, encoding="latin-1", keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
        raise ArquivoInvalido(f"{caminho.name}: CSV ilegível ({e})") from e
    df = _renomear(df, _MAPA_SP156, caminho.name)
    df["recebido_em"] = pd.to_datetime(df["recebido_em"], format="%d/%m/%Y %H:%M", errors="coerce")
    df["canal"] = "sp156"
    return df


def ler_subprefeitura(caminho: Path) -> pd.DataFrame:
    try:
        df = pd.read_excel(caminho, dtype=str, engine="openpyxl")
    except Exception as e:  # openpyxl levanta vários tipos para arquivo corrompido
        raise ArquivoInvalido(f"{caminho.name}: Excel ilegível ({type(e).__name__})") from e
    df = _renomear(df, _MAPA_SUBPREF, caminho.name).fillna("")
    df["recebido_em"] = pd.to_datetime(df["recebido_em"], format="mixed", dayfirst=True, errors="coerce")
    df["canal"] = "subprefeitura"
    return df


def normalizar_app(registros: list[dict], origem: str) -> pd.DataFrame:
    """Relatos do app Zelo já passaram pela IA e pela confirmação do cidadão."""
    if not isinstance(registros, list):
        raise ArquivoInvalido(f"{origem}: esperado uma lista de relatos")
    if not registros:
        return pd.DataFrame(columns=list(_MAPA_APP.values()) + ["canal"])
    df = _renomear(pd.DataFrame(registros), _MAPA_APP, origem).fillna("")
    df["recebido_em"] = pd.to_datetime(df["recebido_em"], errors="coerce", utc=True)
    df["recebido_em"] = df["recebido_em"].dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
    df["canal"] = "app_zelo"
    df["email_cidadao"] = ""  # o app não exporta contato do cidadão (minimização)
    df["consentimento"] = "nao"
    return df


def ler_app_json(caminho: Path) -> pd.DataFrame:
    import json

    try:
        registros = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ArquivoInvalido(f"{caminho.name}: JSON inválido ({e})") from e
    return normalizar_app(registros, caminho.name)


LEITORES = {
    "sp156": ("sp156_*.csv", ler_sp156),
    "subprefeitura": ("subprefeitura_*.xlsx", ler_subprefeitura),
    "app_zelo": ("app_zelo_*.json", ler_app_json),
}


# ---------------------------------------------------------------------------
# Validação e padronização
# ---------------------------------------------------------------------------
def _consentiu(valor: str) -> bool:
    return str(valor).strip().lower() in {"s", "sim", "true", "1", "yes", "x"}


def validar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Retorna (validos, quarentena, duplicados_no_lote)."""
    if df.empty:
        return pd.DataFrame(columns=COLUNAS), pd.DataFrame(columns=["canal", "id_origem", "motivo"]), 0

    df = df.copy()
    for col in ("id_origem", "descricao", "bairro", "email_cidadao", "consentimento",
                "categoria_informada", "urgencia_informada"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()

    df["descricao"] = df["descricao"].str.replace(r"\s+", " ", regex=True)
    df["bairro_original"] = df["bairro"]
    df["bairro"] = df["bairro"].map(normalizar_bairro)

    motivos = pd.Series("", index=df.index)

    def marcar(mascara: pd.Series, motivo: str) -> None:
        motivos.loc[mascara & (motivos == "")] = motivo

    marcar(df["id_origem"] == "", "identificador de origem ausente")
    marcar(df["descricao"].str.len() < TAMANHO_MINIMO_DESCRICAO,
           f"descrição vazia ou curta demais (< {TAMANHO_MINIMO_DESCRICAO} caracteres)")
    marcar(df["bairro"].isna(), "bairro não reconhecido")
    marcar(df["recebido_em"].isna(), "data de abertura inválida")
    app = df["canal"] == "app_zelo"
    marcar(app & ~df["categoria_informada"].isin(CATEGORIAS), "categoria do app inválida")
    marcar(app & ~df["urgencia_informada"].isin(URGENCIAS), "urgência do app inválida")

    quarentena = df[motivos != ""].assign(motivo=motivos[motivos != ""])
    quarentena = quarentena[["canal", "id_origem", "bairro_original", "motivo"]].rename(
        columns={"bairro_original": "bairro_informado"})
    for _, linha in quarentena.iterrows():
        log.warning("Quarentena: %s/%s -> %s", linha["canal"], linha["id_origem"] or "?", linha["motivo"])

    ok = df[motivos == ""].copy()

    # LGPD: o texto só segue adiante já sem CPF, telefone, e-mail ou placa.
    anon = ok["descricao"].map(anonimizar)
    ok["descricao"] = anon.map(lambda t: t[0])
    ok["dados_removidos"] = anon.map(lambda t: ", ".join(t[1]))

    # E-mail só é guardado se for válido E se o cidadão autorizou contato.
    autorizado = ok["consentimento"].map(_consentiu)
    valido = ok["email_cidadao"].map(email_valido)
    for _, linha in ok[autorizado & ~valido & (ok["email_cidadao"] != "")].iterrows():
        log.info("E-mail inválido ignorado em %s/%s (%s)", linha["canal"], linha["id_origem"],
                 mascarar_email(linha["email_cidadao"]))
    ok["email_cidadao"] = ok["email_cidadao"].where(autorizado & valido, "")

    ok["chave"] = [hash_curto(c, i) for c, i in zip(ok["canal"], ok["id_origem"])]

    # Duplicados dentro do mesmo lote: mesmo relato vindo duas vezes (ex.: planilha reenviada).
    assinatura = ok["descricao"].str.lower() + "|" + ok["bairro"]
    dup = ok.duplicated("chave") | assinatura.duplicated()
    duplicados = int(dup.sum())
    if duplicados:
        log.info("%d relato(s) duplicado(s) no lote foram descartados", duplicados)
    ok = ok[~dup]

    return ok[COLUNAS].reset_index(drop=True), quarentena.reset_index(drop=True), duplicados


# ---------------------------------------------------------------------------
# Orquestração da leitura da pasta de entrada
# ---------------------------------------------------------------------------
def _mover(arquivo: Path, destino: Path, run_id: str) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(arquivo), destino / f"{run_id}__{arquivo.name}")
    except OSError as e:
        log.error("Não consegui mover %s para %s: %s", arquivo.name, destino, e)


def ingerir(pasta: Path, run_id: str, df_app_api: pd.DataFrame | None = None,
            mover_arquivos: bool = True) -> ResultadoIngestao:
    pasta.mkdir(parents=True, exist_ok=True)
    quadros: list[pd.DataFrame] = []
    res = ResultadoIngestao(validos=pd.DataFrame(), quarentena=pd.DataFrame())

    if df_app_api is not None:
        quadros.append(df_app_api)
        res.arquivos_ok.append("API do app Zelo")

    for canal, (padrao, leitor) in LEITORES.items():
        if canal == "app_zelo" and df_app_api is not None:
            continue  # a API já trouxe os relatos do app; o arquivo seria redundante
        arquivos = sorted(pasta.glob(padrao))
        if not arquivos:
            log.warning("Canal '%s' sem arquivo na entrada (%s). Seguindo com os demais.", canal, padrao)
            res.canais_sem_arquivo.append(canal)
            continue
        for arq in arquivos:
            try:
                df = leitor(arq)
                quadros.append(df)
                res.arquivos_ok.append(arq.name)
                log.info("Lido %s: %d linha(s)", arq.name, len(df))
                if mover_arquivos:
                    _mover(arq, pasta / "processados", run_id)
            except ArquivoInvalido as e:
                log.error("Arquivo rejeitado: %s", e)
                res.arquivos_com_erro.append(arq.name)
                if mover_arquivos:
                    _mover(arq, pasta / "com_erro", run_id)

    bruto = pd.concat(quadros, ignore_index=True) if quadros else pd.DataFrame()
    res.lidos = len(bruto)
    res.validos, res.quarentena, res.duplicados_no_lote = validar(bruto)
    return res
