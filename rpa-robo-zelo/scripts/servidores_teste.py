"""Servidores LOCAIS de teste (só biblioteca padrão), usados na validação.

- SMTPLocal: servidor SMTP mínimo em 127.0.0.1 que aceita e guarda as mensagens.
  Permite testar o modo EMAIL_MODO=smtp sem conta de e-mail.
  Também pode ser usado à mão: `python -m scripts.servidores_teste` e, em outro
  terminal, rode o robô com SMTP_HOST=127.0.0.1 SMTP_PORTA=2525 SMTP_TLS=0.
- HTTPLocal: imita a API do Open-Meteo, com a opção de falhar nas primeiras
  chamadas (HTTP 503) para demonstrar o retry com espera.
"""

from __future__ import annotations

import json
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _SMTPHandler(socketserver.StreamRequestHandler):
    def _env(self, linha: str) -> None:
        self.wfile.write((linha + "\r\n").encode())

    def handle(self) -> None:
        self._env("220 smtp-local Zelo pronto")
        dados, em_data = [], False
        while True:
            bruto = self.rfile.readline()
            if not bruto:
                return
            linha = bruto.decode("utf-8", "replace").rstrip("\r\n")
            if em_data:
                if linha == ".":
                    em_data = False
                    self.server.mensagens.append("\n".join(dados))
                    dados = []
                    self._env("250 mensagem aceita")
                else:
                    dados.append(linha[1:] if linha.startswith("..") else linha)
                continue
            cmd = linha.split(" ", 1)[0].upper()
            if cmd in ("EHLO", "HELO"):
                self._env("250 smtp-local")
            elif cmd in ("MAIL", "RCPT", "RSET", "NOOP"):
                self._env("250 ok")
            elif cmd == "DATA":
                em_data = True
                self._env("354 envie a mensagem")
            elif cmd == "QUIT":
                self._env("221 tchau")
                return
            else:
                self._env("502 comando não suportado")


class SMTPLocal(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, porta: int = 2525):
        super().__init__(("127.0.0.1", porta), _SMTPHandler)
        self.mensagens: list[str] = []

    def iniciar(self) -> "SMTPLocal":
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return self

    def parar(self) -> None:
        self.shutdown()
        self.server_close()


class HTTPLocal(HTTPServer):
    """Open-Meteo de mentira: responde `chuva_mm` e falha nas `falhas_iniciais` primeiras chamadas."""

    def __init__(self, porta: int = 8765, chuva_mm: float = 35.0, falhas_iniciais: int = 0):
        self.chuva_mm = chuva_mm
        self.falhas_restantes = falhas_iniciais
        self.chamadas = 0
        servidor = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                servidor.chamadas += 1
                if servidor.falhas_restantes > 0:
                    servidor.falhas_restantes -= 1
                    self.send_response(503)
                    self.end_headers()
                    return
                corpo = json.dumps({"daily": {"precipitation_sum": [servidor.chuva_mm]}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(corpo)

            def log_message(self, *_):
                pass

        super().__init__(("127.0.0.1", porta), Handler)

    def iniciar(self) -> "HTTPLocal":
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return self

    def parar(self) -> None:
        self.shutdown()
        self.server_close()


if __name__ == "__main__":
    import time

    s = SMTPLocal().iniciar()
    print("SMTP local ouvindo em 127.0.0.1:2525 (Ctrl+C para sair)")
    vistos = 0
    try:
        while True:
            time.sleep(1)
            for m in s.mensagens[vistos:]:
                assunto = next((l for l in m.splitlines() if l.startswith("Subject:")), "Subject: ?")
                print("Recebido:", assunto)
            vistos = len(s.mensagens)
    except KeyboardInterrupt:
        s.parar()
