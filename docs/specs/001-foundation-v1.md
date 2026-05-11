# 001 - Foundation v1: bootstrap, RAG, agente WhatsApp y backoffice

## Contexto y objetivo

Biomont es un laboratorio veterinario de Peru. Sus representantes tecnico
comerciales (RTCs) en distintos paises necesitan consultar informacion de
productos por WhatsApp. Necesitamos:

1. Un **agente** WhatsApp que responda solo con informacion validada,
   citando documento y similitud.
2. Un **backoffice** (API + frontend) para que cientificos carguen PDFs,
   se procesen (ETL con docling) y queden disponibles para el RAG.
3. Un sistema de **tickets** para cuando el agente no sabe algo.
4. **Filtrado regional** por pais habilitado por RTC.
5. **System prompt editable** desde la web, versionado.
6. **Postgres + pgvector** en Railway, externo al docker-compose.

## Alcance / fuera de alcance

**En alcance v1**:

- Bootstrap del monorepo (estructura, docker-compose, .env.example,
  scripts, skill `manage-biomont-db`).
- Migraciones SQL versionadas (`001`, `002`, `003` + downs).
- Paquete comun `services/common` con cliente Postgres async, schemas
  pydantic, settings y wrappers LangChain.
- `services/backoffice-api` (FastAPI): auth JWT + RBAC minimo, CRUD de
  documentos / RTCs / system prompt / tickets, ETL con docling y
  embeddings via LangChain, endpoints de analytics minimos.
- `services/agent` (FastAPI): webhook Meta Cloud API con verificacion
  HMAC, RTC guard, pipeline LCEL (retriever filtrado + structured
  output), ticket on miss, decision log.
- `services/backoffice-web` (Next.js 16): login + paginas CRUD basicas
  para documentos / RTCs / prompt / tickets + dashboard minimo.
- Suite de tests con pytest y mocks de OpenAI / docling / WhatsApp.

**Fuera de alcance v1**:

- Almacenamiento de PDFs en bucket.
- Heatmap visual avanzado.
- SSO / Clerk / Auth0.
- Multi-idioma del agente mas alla de espanol/ingles via prompt.
- Fine-tuning del modelo.

## Requisitos funcionales

- **RF-1**: el agente solo responde a numeros presentes en `rtc_users`
  con `enabled = true`. Caso contrario, responde con un mensaje neutro
  y registra el intento.
- **RF-2**: el agente solo responde citando documentos y similitud.
  Si el modelo no produce citaciones validas, marca `low_confidence` y
  no envia la respuesta.
- **RF-3**: si la mejor similitud queda por debajo del umbral
  configurable (default 0.75), el agente crea un ticket `no_info` y
  responde "no tengo esa info".
- **RF-4**: el retrieval filtra por `country_iso IN user_countries OR
  country_iso IS NULL` (documentos globales).
- **RF-5**: el system prompt activo se lee de la tabla
  `system_prompts WHERE is_active = true` con cache de 60s. Editar
  desde la web crea una nueva version y deja audit log.
- **RF-6**: subir un PDF en el backoffice dispara docling -> markdown
  -> chunks -> embeddings -> `document_chunks`. El usuario puede
  previsualizar el markdown.
- **RF-7**: roles backoffice: `admin`, `scientist`, `viewer`.
- **RF-8**: dashboard minimo: total consultas, uso por pais, latencia
  media, top productos consultados, gaps (`decision=no_match`).

## Requisitos no funcionales

- **RNF-1**: latencia objetivo del agente p95 < 6s end to end.
- **RNF-2**: secrets nunca en logs ni en mensajes (cumple
  [logging-policy-observability](../../.cursor/rules/logging-policy-observability.mdc)).
- **RNF-3**: logs estructurados JSON via `structlog` con `component`,
  `event`, `request_id`.
- **RNF-4**: tests en CI no dependen de OpenAI, Meta ni docling reales
  (mocks).
- **RNF-5**: capas separadas `api / agent / db / integrations /
  schemas` en cada servicio Python (cumple
  [architecture-clean-fastapi](../../.cursor/rules/architecture-clean-fastapi.mdc)).

## Criterios de aceptacion (Given/When/Then)

- **CA-1: RTC autorizado pregunta y recibe respuesta con cita**
  - **Given** un RTC con telefono `+51999...`, `enabled=true`, pais
    `PE` habilitado y un documento validado de producto X en PE
  - **When** envia "que dosis tiene producto X"
  - **Then** el agente responde con la dosis citando titulo del
    documento y similitud, persiste mensaje + `agent_decisions`
    con `decision=answered`.

- **CA-2: RTC no autorizado**
  - **Given** un telefono que no esta en `rtc_users`
  - **When** envia un mensaje
  - **Then** el agente responde "no estas autorizado" y registra la
    decision como `blocked`. No se llama a OpenAI.

- **CA-3: Agente no encuentra info**
  - **Given** un RTC autorizado con pais MX, sin documentos MX ni
    globales del producto consultado
  - **When** envia una pregunta
  - **Then** el agente crea un `tickets(type=no_info, status=open)`,
    responde "no tengo esa info, abri ticket #N" y registra
    `decision=no_match`.

- **CA-4: Carga de PDF**
  - **Given** un usuario backoffice con rol `scientist`
  - **When** sube un PDF de producto
  - **Then** se persiste `documents` en estado `processing`, se
    extrae markdown via docling, se generan chunks + embeddings, y
    pasa a `validated`. El audit log refleja la accion.

- **CA-5: Edicion del system prompt**
  - **Given** un usuario `admin`
  - **When** edita el system prompt activo
  - **Then** se crea una nueva version en `system_prompts`, se
    marca `is_active=true` en la nueva y `false` en la anterior,
    el audit log registra el cambio, y el agente usa la nueva
    version en el siguiente request (con cache de hasta 60s).

## Diseno tecnico

Ver el [plan de bootstrap](../../README.md#stack) y el documento de
plan en `~/.cursor/plans/biomont_v1_bootstrap_*.plan.md`.

Capas por servicio Python:

- `app/api/`: routers FastAPI, validacion y autorizacion.
- `app/agent/` (solo agente) o `app/services/` (backoffice): casos de
  uso.
- `app/db/`: repositorios sobre Postgres.
- `app/integrations/`: clientes externos (OpenAI/LangChain, Meta).
- `app/schemas/`: contratos pydantic.

Pipeline del agente (LCEL):

```
build_retriever(rtc_user) -> top_k chunks
   -> ChatPromptTemplate (system_prompt activo, chunks, query)
   -> ChatOpenAI(gpt-4o-mini).with_structured_output(RagAnswer)
   -> validate citations & threshold
   -> persist message + decision + (ticket si aplica)
   -> reply via Meta Cloud API
```

## Migraciones necesarias

`Migraciones necesarias: si`

- `migrations/001_extensions_and_core.sql` (+ down): pgvector,
  pgcrypto, `countries`, `bo_users`, `bo_audit_log`, `rtc_users`,
  `rtc_user_countries`.
- `migrations/002_rag.sql` (+ down): `documents`, `document_chunks`
  con `vector(1536)`, indice IVFFlat cosine.
- `migrations/003_conversations_tickets.sql` (+ down):
  `system_prompts`, `conversations`, `messages`, `agent_decisions`,
  `tickets`.

**Evidencia de estructura actual**: la base esta vacia (recien
provisionada en Railway). Validado al inicio del proyecto. Las
migraciones se aplican desde local via `scripts/apply_migration.sh`.

## Plan de pruebas

- `services/backoffice-api`:
  - Tests HTTP (`pytest` + `httpx`): login, RBAC, CRUD documentos,
    CRUD RTCs, CRUD prompt, upload PDF (mock docling), tickets.
  - Test unitario del splitter + chunker.
  - Test del cliente OpenAI con `FakeEmbeddings`.
- `services/agent`:
  - Test del webhook: firma valida/invalida, autorizado/no
    autorizado, branch low_confidence, branch answered, branch
    no_match.
  - Test del retriever con vectores fake.
  - Test del pipeline LCEL con `FakeListChatModel`.

## Observabilidad

- `structlog` JSON con keys minimos `component`, `event`,
  `request_id`.
- Latencia del pipeline del agente loggeada por etapa.
- Tickets creados loggean `ticket_id`, `reason`, `top_similarity`.

## Riesgos y rollback

- **Riesgo**: pgvector no disponible. Mitigacion: la migracion 001
  hace `CREATE EXTENSION IF NOT EXISTS vector` y falla rapido si el
  plan de Railway no lo permite. Plan B: cambiar a `pgvecto.rs` o un
  servicio dedicado.
- **Riesgo**: Meta WBA en review. Mitigacion: usar numero de test
  en desarrollo. La capa `whatsapp_client` esta abstraida para
  permitir un `FakeWhatsAppClient` en tests.
- **Riesgo**: re-procesar PDFs cuesta caro en embeddings. Mitigacion:
  idempotencia por `content_sha256` en `documents`.
- **Rollback**: cada migracion `NNN_*.sql` tiene su `NNN_*.down.sql`.
  El despliegue de codigo viejo + correr el `.down.sql` revierte la
  feature.
