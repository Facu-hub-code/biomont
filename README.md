# Biomont

Agente WhatsApp + backoffice RAG para consultar informacion de productos
del laboratorio veterinario **Biomont** (Peru). Pensado para que sus
representantes tecnico-comerciales (RTCs) consulten datos validados desde
WhatsApp con citacion obligatoria de la fuente.

## Modulos

| Servicio | Puerto local | Stack | Rol |
| --- | --- | --- | --- |
| `services/agent` | 8001 | FastAPI + LangChain + OpenAI | Webhook Meta Cloud API, RAG con citaciones, tickets |
| `services/backoffice-api` | 8002 | FastAPI + Docling + LangChain | ETL de PDFs, CRUD documentos / RTCs / prompt / tickets, analytics |
| `services/backoffice-web` | 3000 | Next.js 16 + Tailwind | UI del backoffice |

La base **Postgres + pgvector** vive en **Railway** y queda fuera del
docker-compose: los servicios se conectan via `DATABASE_URL`.

## Arquitectura

```
+-----------------+       +------------------+      +-----------------+
| Meta WhatsApp   |<----->| agent-service    |<---->|  Postgres +     |
| Cloud API       |       | FastAPI/LangChain|      |  pgvector       |
+-----------------+       +------------------+      |  (Railway)      |
                                  ^                  +-----------------+
                                  |  comparte DB             ^
                                  v                          |
                          +------------------+               |
                          | backoffice-api   |---------------+
                          | FastAPI + ETL    |
                          +------------------+
                                  ^
                                  | HTTP/JSON
                                  v
                          +------------------+
                          | backoffice-web   |
                          | Next.js          |
                          +------------------+
```

## Stack

- Python 3.12, FastAPI, asyncpg, pgvector, structlog.
- LangChain (`langchain-core`, `langchain-openai`,
  `langchain-text-splitters`).
- Next.js 16 (App Router), Tailwind.
- OpenAI `gpt-4o-mini` + `text-embedding-3-small` (1536 dims).
- Meta WhatsApp Business Cloud API (Graph API v20.0).

Reglas y conveciones del repo en `.cursor/rules/`:

- [architecture-clean-fastapi](.cursor/rules/architecture-clean-fastapi.mdc)
- [naming-conventions-python](.cursor/rules/naming-conventions-python.mdc)
- [testing-policy-python](.cursor/rules/testing-policy-python.mdc)
- [logging-policy-observability](.cursor/rules/logging-policy-observability.mdc)
- [dependency-constraints](.cursor/rules/dependency-constraints.mdc)

Specs en [`docs/specs/`](docs/specs/README.md). La spec v1 vive en
[001-foundation-v1.md](docs/specs/001-foundation-v1.md).

## Bootstrap (primera vez)

### 1. Variables de entorno

```bash
cp .env.example .env
# Editar .env con valores reales: DATABASE_URL, OPENAI_API_KEY,
# WHATSAPP_*, JWT_SECRET, etc.
```

Variables criticas:

| Variable | Donde se usa | Ejemplo |
| --- | --- | --- |
| `DATABASE_URL` | todos | `postgres://user:pass@host:5432/biomont` |
| `OPENAI_API_KEY` | agente, backoffice-api (ETL) | `sk-...` |
| `OPENAI_CHAT_MODEL` | agente | `gpt-4o-mini` |
| `OPENAI_EMBEDDINGS_MODEL` | agente, ETL | `text-embedding-3-small` |
| `WHATSAPP_PHONE_NUMBER_ID` | agente | el id que entrega Meta |
| `WHATSAPP_ACCESS_TOKEN` | agente | token long-lived |
| `WHATSAPP_VERIFY_TOKEN` | agente | string elegido por vos |
| `WHATSAPP_APP_SECRET` | agente | secret de la app de Meta para HMAC |
| `JWT_SECRET` | backoffice-api | string >= 32 chars |
| `AGENT_SIMILARITY_THRESHOLD` | agente | `0.75` |
| `AGENT_TOP_K` | agente | `6` |

### 2. Linkear Railway (proyecto donde vive el Postgres)

```bash
railway link
railway status
```

### 3. Aplicar migraciones contra la instancia remota

Las migraciones SQL viven en [`migrations/`](migrations) y se aplican una
por una con el script de ayuda:

```bash
railway run ./scripts/apply_migration.sh 001
railway run ./scripts/apply_migration.sh 002
railway run ./scripts/apply_migration.sh 003
```

Para rollback manual (no recomendado en prod):

```bash
railway run ./scripts/apply_migration.sh 003 --down
```

Seed inicial opcional (admin + system prompt v1):

```bash
railway run psql -f scripts/seed_dev.sql
```

> El password del admin sembrado es `biomont-admin` y **debe cambiarse**
> en la primera sesion.

### 4. Levantar los servicios

```bash
docker compose up --build
```

Endpoints:

- Agent: `http://localhost:8001` (`GET /health`, webhook en
  `/whatsapp/webhook`).
- Backoffice API: `http://localhost:8002` (Swagger en `/docs`).
- Backoffice Web: `http://localhost:3000`.

Verificacion rapida:

```bash
curl http://localhost:8001/health   # {"status":"ok"}
curl http://localhost:8002/health   # {"status":"ok"}
```

### 5. Configurar el webhook en Meta

En el dashboard de la app de Meta:

- `Callback URL`: `https://<tu-dominio-publico>/whatsapp/webhook`
- `Verify token`: el valor de `WHATSAPP_VERIFY_TOKEN`
- Suscribirse al campo `messages`.

Para desarrollo, exponer el agente con `ngrok http 8001` y usar la URL
publica.

## Desarrollo local sin docker

Cada servicio Python tiene su propio `pyproject.toml`. Los servicios
**`agent` y `backoffice-api` comparten el namespace `app`**, asi que
usan **venvs separados**:

```bash
# Agent
cd services/agent
python -m venv .venv && source .venv/bin/activate
pip install -e ../common -e ".[dev]"
uvicorn app.main:app --reload --port 8001
```

```bash
# Backoffice API
cd services/backoffice-api
python -m venv .venv && source .venv/bin/activate
pip install -e ../common -e ".[dev]"
# Para correr el ETL real con docling agregar el extra:
# pip install -e ".[dev,etl]"
uvicorn app.main:app --reload --port 8002
```

```bash
# Backoffice Web
cd services/backoffice-web
npm install
npm run dev
```

## Tests

Cada servicio Python tiene su suite con `pytest`. Los tests no llaman a
OpenAI / Meta / docling reales (uso de mocks/fakes).

```bash
# En el venv del servicio
python -m pytest -q
```

Cobertura por servicio (v1):

- `services/common`: chunker / splitter.
- `services/agent`: pipeline LCEL, orquestador (answered / blocked /
  no_match / low_confidence) y webhook (HMAC + ruteo).
- `services/backoffice-api`: hashing + JWT, ETL con docling mock,
  endpoints HTTP de auth.

## Skills relacionadas

- [`manage-biomont-db`](.cursor/skills/manage-biomont-db/SKILL.md):
  operacion agentica sobre Postgres + pgvector en Railway (listar
  tablas, aplicar migraciones, inspeccionar chunks).

## Troubleshooting

- **`extension "vector" does not exist`**: el plan de Railway no tiene
  pgvector habilitado. Solucion: solicitar el upgrade del plan o usar
  un Postgres con la extension disponible.
- **Webhook devuelve 401 "invalid signature"**: verificar que
  `WHATSAPP_APP_SECRET` coincida con el `App Secret` de la app de Meta.
- **El agente responde "no estas autorizado"**: el numero no esta en
  `rtc_users` con `enabled=true`, o no tiene paises asignados que
  habiliten algun documento. Cargar al RTC desde el backoffice.
- **El agente responde "no tengo esa info" siempre**: revisar que
  haya documentos en estado `validated`, que los chunks tengan
  embeddings y que `country_iso` coincida con los del RTC.
- **`tiktoken` falla sin red**: el `text_splitter` cae a un encoder
  bundled (`cl100k_base`) y, en ultimo caso, a un heuristico por
  caracteres. Para mejor precision en produccion, dar acceso a internet
  durante el primer `pip install`.

## Fuera de alcance v1

Ver [`docs/specs/001-foundation-v1.md`](docs/specs/001-foundation-v1.md#alcance--fuera-de-alcance).
