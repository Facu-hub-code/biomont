# =====================================================================
# agent - FastAPI + LangChain (Meta WhatsApp Cloud API)
# Build context: repositorio raiz.
# =====================================================================
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY services/common /app/services/common
COPY services/agent /app/services/agent

RUN pip install -e /app/services/common \
    && pip install -e /app/services/agent

WORKDIR /app/services/agent

EXPOSE 8001

# Railway injecta PORT; compose local sigue usando 8001 si no viene seteado.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
