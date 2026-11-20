FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

# Usuário sem privilégios de root
RUN useradd --create-home zelo && mkdir -p /app/data && chown -R zelo /app
USER zelo

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\",\"8000\")}/health')"

# PORT é definida automaticamente pelo Render; localmente usa 8000.
# --no-proxy-headers: o IP real é obtido de forma segura em core/dependencias.py
# (X-Forwarded-For contado a partir da direita, com PROXIES_CONFIAVEIS).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]
