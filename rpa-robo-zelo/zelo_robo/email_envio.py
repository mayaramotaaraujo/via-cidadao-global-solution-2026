"""TEMA 4: e-mail automatizado.

Três tipos de mensagem saem do robô:
- cidadão: confirmação de protocolo (só se ele autorizou contato);
- órgão: lista de despacho do dia, com a planilha Excel em anexo;
- coordenação: relatório da execução e fila de revisão humana.

Modos (variável EMAIL_MODO no .env):
- "arquivo" (padrão): monta a mensagem completa e salva como .eml em
  saida/<execução>/outbox/. Permite rodar e avaliar sem conta de e-mail.
- "smtp": envia de verdade (ex.: sandbox gratuito do Mailtrap ou Gmail com
  senha de app). Usuário e senha ficam só no .env.

Resiliência: timeout, 3 tentativas com espera exponencial. Se ainda assim
falhar, a mensagem fica salva com status "pendente" e é reenviada na próxima
execução. O banco garante que nada é enviado duas vezes.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
import time
import unicodedata
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

from .banco import Banco
from .config import Config
from .privacidade import mascarar_email

log = logging.getLogger("zelo.email")

_JA_ENTREGUE = {"enviado", "salvo_arquivo"}


def montar(remetente: str, destinatario: str, assunto: str, corpo: str,
           anexos: list[Path] | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = remetente
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg.set_content(corpo)
    for anexo in anexos or []:
        if not anexo.exists():
            log.warning("Anexo %s não existe; e-mail segue sem ele", anexo.name)
            continue
        if anexo.suffix == ".xlsx":
            tipo, sub = "application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif anexo.suffix == ".md":
            tipo, sub = "text", "markdown"
        else:
            tipo, sub = "application", "octet-stream"
        msg.add_attachment(anexo.read_bytes(), maintype=tipo, subtype=sub, filename=anexo.name)
    return msg


class Carteiro:
    def __init__(self, cfg: Config, banco: Banco, run_id: str, pasta_outbox: Path):
        self.cfg = cfg
        self.banco = banco
        self.run_id = run_id
        self.outbox = pasta_outbox
        self.contagem = {"enviado": 0, "salvo_arquivo": 0, "pendente": 0, "ignorado_ja_enviado": 0}

    # -- canal de envio ------------------------------------------------------
    def _smtp(self, msg: EmailMessage) -> None:
        if not self.cfg.smtp_host:
            raise smtplib.SMTPException("SMTP_HOST não configurado")
        with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_porta, timeout=self.cfg.smtp_timeout_s) as s:
            if self.cfg.smtp_tls:
                s.starttls(context=ssl.create_default_context())
            if self.cfg.smtp_usuario:
                s.login(self.cfg.smtp_usuario, self.cfg.smtp_senha)
            s.send_message(msg)

    def _salvar_eml(self, msg: EmailMessage, nome: str) -> Path:
        self.outbox.mkdir(parents=True, exist_ok=True)
        ascii_ = "".join(c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c))
        seguro = "".join(c if (c.isascii() and c.isalnum()) or c in "-_." else "_" for c in ascii_).strip("_")
        while "__" in seguro:
            seguro = seguro.replace("__", "_")
        caminho = self.outbox / f"{seguro}.eml"
        caminho.write_bytes(msg.as_bytes(policy=policy.SMTP))
        return caminho

    def _entregar(self, msg: EmailMessage) -> tuple[str, int, str | None]:
        """Retorna (status, tentativas, erro)."""
        if self.cfg.email_modo != "smtp":
            return "salvo_arquivo", 1, None
        erro = None
        for n in range(1, self.cfg.smtp_tentativas + 1):
            try:
                self._smtp(msg)
                return "enviado", n, None
            except smtplib.SMTPAuthenticationError as e:
                erro = f"autenticação recusada ({e.smtp_code})"
                log.error("SMTP: %s. Verifique SMTP_USUARIO/SMTP_SENHA no .env", erro)
                return "pendente", n, erro
            except (smtplib.SMTPException, OSError) as e:
                erro = f"{type(e).__name__}: {e}"
                log.warning("SMTP falhou na tentativa %d/%d: %s", n, self.cfg.smtp_tentativas, erro)
                if n < self.cfg.smtp_tentativas:
                    time.sleep(self.cfg.espera_retry_s * 2 ** (n - 1))
        return "pendente", self.cfg.smtp_tentativas, erro

    # -- API pública ---------------------------------------------------------
    def enviar(self, tipo: str, referencia: str, destinatario: str, assunto: str, corpo: str,
               anexos: list[Path] | None = None) -> str:
        anterior = self.banco.envio(tipo, referencia)
        if anterior and anterior["status"] in _JA_ENTREGUE:
            self.contagem["ignorado_ja_enviado"] += 1
            log.debug("E-mail %s/%s já entregue antes; não reenviado", tipo, referencia)
            return anterior["status"]

        msg = montar(self.cfg.smtp_remetente, destinatario, assunto, corpo, anexos)
        status, tentativas, erro = self._entregar(msg)
        # Guardamos o .eml sempre: é a evidência no modo arquivo e a fila de reenvio no modo smtp.
        eml = self._salvar_eml(msg, f"{tipo}_{referencia}")
        self.banco.registrar_envio(tipo, referencia, mascarar_email(destinatario), assunto, status,
                                   tentativas, self.run_id, str(eml), erro)
        self.contagem[status] += 1
        nivel = logging.INFO if status in _JA_ENTREGUE else logging.ERROR
        log.log(nivel, "E-mail %s para %s: %s", tipo, mascarar_email(destinatario), status)
        return status

    def reenviar_pendentes(self) -> int:
        """Tenta de novo o que falhou em execuções anteriores (só no modo smtp)."""
        if self.cfg.email_modo != "smtp":
            return 0
        reenviados = 0
        for p in self.banco.envios_pendentes():
            caminho = Path(p["arquivo_eml"] or "")
            if not caminho.exists():
                log.error("Pendente %s/%s sem arquivo .eml; precisa de revisão manual", p["tipo"], p["referencia"])
                continue
            msg = BytesParser(policy=policy.default).parse(caminho.open("rb"))
            status, tentativas, erro = self._entregar(msg)
            self.banco.registrar_envio(p["tipo"], p["referencia"], p["destinatario"], p["assunto"],
                                       status, tentativas, self.run_id, str(caminho), erro)
            if status == "enviado":
                reenviados += 1
                if p["tipo"] == "cidadao":
                    self.banco.apagar_contato(p["referencia"])
        if reenviados:
            log.info("%d e-mail(s) pendente(s) de execuções anteriores reenviado(s)", reenviados)
        return reenviados
