# =====================================================================
# backoffice-api - FastAPI + Docling + LangChain
# Build context: repositorio raiz (necesita acceso a services/common).
# =====================================================================
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias de sistema minimas para asyncpg + docling + argon2.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        poppler-utils \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY services/common /app/services/common
COPY services/backoffice-api /app/services/backoffice-api

RUN pip install -e /app/services/common \
    && pip install -e "/app/services/backoffice-api[etl]"

WORKDIR /app/services/backoffice-api

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
