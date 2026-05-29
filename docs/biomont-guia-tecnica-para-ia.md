# Biomont — Guía técnica para sistemas de IA

> **Propósito de este documento:** servir como contexto completo y autocontenido para que un modelo de lenguaje (o cualquier agente de IA) responda preguntas técnicas, operativas y de arquitectura sobre el proyecto **Biomont** sin necesidad de explorar el repositorio en tiempo real.
>
> **Última actualización de referencia:** mayo 2026 · estado del código post-specs 001–010 (migraciones 001–008 aplicadas).

---

## Tabla de contenidos

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Dominio de negocio](#2-dominio-de-negocio)
3. [Arquitectura del sistema](#3-arquitectura-del-sistema)
4. [Monorepo y servicios](#4-monorepo-y-servicios)
5. [Base de datos PostgreSQL](#5-base-de-datos-postgresql)
6. [ETL e ingestión de documentos](#6-etl-e-ingestión-de-documentos)
7. [Corpus documental y RAG](#7-corpus-documental-y-rag)
8. [Agente conversacional](#8-agente-conversacional)
9. [Tipos de preguntas y comportamiento esperado](#9-tipos-de-preguntas-y-comportamiento-esperado)
10. [Canal WhatsApp e integración Meta](#10-canal-whatsapp-e-integración-meta)
11. [Backoffice (API + Web)](#11-backoffice-api--web)
12. [Configuración, variables de entorno y parámetros](#12-configuración-variables-de-entorno-y-parámetros)
13. [Despliegue e infraestructura](#13-despliegue-e-infraestructura)
14. [Observabilidad, auditoría y debugging](#14-observabilidad-auditoría-y-debugging)
15. [Evolución del proyecto (historial de specs)](#15-evolución-del-proyecto-historial-de-specs)
16. [Fuera de alcance y roadmap](#16-fuera-de-alcance-y-roadmap)
17. [Glosario](#17-glosario)
18. [Mapa de archivos clave](#18-mapa-de-archivos-clave)

---

## 1. Resumen ejecutivo

**Biomont** es un sistema de **agente conversacional por WhatsApp** combinado con un **backoffice de gestión de conocimiento (RAG)** para el laboratorio veterinario **Biomont (Perú)**.

### Problema que resuelve

Los **Representantes Técnicos Comerciales (RTCs)** necesitan consultar información validada sobre productos veterinarios (dosis, protocolos, contraindicaciones, comparativas, etc.) mientras están en campo. La información vive en PDFs estructurados (fichas técnicas, bitácoras de campo, balotarios de preguntas). El agente permite consultar esa información por WhatsApp con **citación obligatoria de la fuente documental**.

### Principios no negociables del agente

1. **Solo responde con documentos validados** — nunca inventa información clínica o comercial.
2. **Citación obligatoria** — toda respuesta exitosa incluye referencia al documento fuente (título en bloque "Fuentes:").
3. **Acceso restringido** — solo responde a teléfonos registrados y habilitados en `rtc_users`.
4. **Filtrado regional** — cada RTC solo ve documentos de sus países habilitados (más documentos globales).
5. **Abstención con ticket** — si no hay evidencia suficiente, responde "No tengo esa información" y crea un ticket para revisión humana.
6. **Resolución de producto determinista** — productos homónimos (ej. `Proteggo M` vs `Proteggo 3M`) se resuelven con matching trigram, no con suposiciones del LLM.

### Stack tecnológico principal

| Capa | Tecnología |
|------|------------|
| Agente | Python 3.12, FastAPI, LangGraph, LangChain, OpenAI |
| Backoffice API | Python 3.12, FastAPI, Docling (ETL PDF), LangChain |
| Backoffice Web | Next.js 16 (App Router), React 19, Tailwind |
| Base de datos | PostgreSQL en Railway + pgvector + pg_trgm + unaccent |
| LLM | OpenAI `gpt-4o-mini` (chat + clasificación) |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dimensiones) |
| Mensajería | Meta WhatsApp Business Cloud API (Graph API v20.0) |
| Deploy | Docker + Railway (3 servicios independientes) |

---

## 2. Dominio de negocio

### Actores

| Actor | Rol | Interacción |
|-------|-----|-------------|
| **RTC** | Representante técnico-comercial de Biomont | Consulta por WhatsApp |
| **Científico / Admin** | Equipo interno Biomont | Carga PDFs, gestiona productos, audita decisiones |
| **Viewer** | Operador de solo lectura | Consulta analytics, conversaciones, tickets |

### Catálogo de productos

- Objetivo: **~100 productos veterinarios** de la línea Biomont.
- Cada producto tiene típicamente **3 documentos PDF**:
  - **Ficha técnica** (`ficha_tecnica`) — ~3 páginas, información formal/regulatoria.
  - **Bitácora** (`bitacora`) — ~35 páginas, material de campo, protocolos, comparativas.
  - **Balotario** (`balotario`) — ~2 páginas, formato pregunta-respuesta (FAQ).
- Los productos son entidades de primera clase en la tabla `products`, con **aliases** (nombres coloquiales, colores, duraciones: "el verde", "el de 3 meses", etc.).

### Alcance geográfico

Países soportados (ISO2): **PE, BO, EC, CO, CL, MX, AR**.

- Los documentos pueden ser **globales** (`country_iso IS NULL`) o **regionales** (ISO2 específico).
- Cada RTC tiene países habilitados en `rtc_user_countries`.
- El retrieval filtra: `country_iso IN (países del RTC) OR country_iso IS NULL`.

### Ejemplo clínico crítico

`Proteggo M` y `Proteggo 3M` son productos distintos con implicaciones clínicas diferentes (ej. estudios de seguridad en gestación). Confundirlos es **clínicamente peligroso**. Por eso existe `ProductResolver` determinista con pg_trgm y repregunta en caso de ambigüedad.

---

## 3. Arquitectura del sistema

### Diagrama de componentes

```
┌─────────────────────┐
│ Meta WhatsApp       │
│ Cloud API           │
└─────────┬───────────┘
          │ webhook POST/GET + Graph API send
          ▼
┌─────────────────────┐       ┌──────────────────────────┐
│ agent-service       │◄─────►│ PostgreSQL + pgvector    │
│ :8001               │  SQL  │ (Railway, fuera de       │
│ FastAPI + LangGraph │       │  docker-compose)         │
└─────────┬───────────┘       └────────────▲─────────────┘
          │                                │
          │                    ┌───────────┴─────────────┐
          │                    │ backoffice-api          │
          │                    │ :8002                   │
          │                    │ FastAPI + ETL (Docling) │
          │                    └───────────▲─────────────┘
          │                                │ HTTP/JSON + JWT
          │                    ┌───────────┴─────────────┐
          │                    │ backoffice-web          │
          │                    │ :3000 (Next.js)         │
          └────────────────────┴─────────────────────────┘
                               OpenAI API (chat + embeddings)
```

### Flujos principales

#### Flujo RTC (WhatsApp)

1. RTC envía mensaje de texto → Meta Cloud API.
2. Meta reenvía webhook → `POST /whatsapp/webhook` (agente).
3. Verificación HMAC-SHA256 con `WHATSAPP_APP_SECRET`.
4. Lookup en `rtc_users` por `phone_e164`.
5. Si no autorizado → respuesta neutra + `agent_decisions.decision = blocked` (sin llamar a OpenAI).
6. Si autorizado → orquestador ejecuta grafo LangGraph → persistencia → respuesta vía Graph API.

#### Flujo ETL (Backoffice)

1. Científico/admin sube PDF desde backoffice web.
2. `POST /documents` (multipart) → backoffice-api.
3. Pipeline ETL: Docling → markdown → chunking estructural → embeddings → Postgres.
4. Documento queda en estado `validated` con secciones y `knowledge_chunks`.

#### Flujo Playground (prueba interna)

1. Operador backoffice envía mensaje desde UI de conversaciones.
2. `backoffice-web` → `POST /playground/messages` (JWT).
3. `backoffice-api` proxy → `POST http://agent:8001/internal/playground/messages` (header `X-Playground-Secret`).
4. Mismo grafo que WhatsApp, pero **sin envío por WhatsApp** y con RTC seleccionado manualmente.

### Paquete compartido `biomont-common`

Ambos servicios Python dependen de `services/common` (paquete `biomont-common`):

- Pool asyncpg y transacciones.
- Repositorios SQL (RAG, productos, RTC, conversaciones, config agente).
- Schemas Pydantic compartidos.
- Chunkers, factories OpenAI, settings, logging structlog.

**Importante:** `agent` y `backoffice-api` comparten el namespace Python `app` → requieren **entornos virtuales separados** en desarrollo local.

---

## 4. Monorepo y servicios

### Estructura de carpetas

```
biomont/
├── services/
│   ├── agent/              # Webhook WhatsApp + grafo LangGraph
│   ├── backoffice-api/     # ETL, CRUD, auth JWT, analytics
│   ├── backoffice-web/     # UI Next.js
│   └── common/             # biomont-common (paquete compartido)
├── migrations/             # SQL versionado (001–008)
├── scripts/                # Migraciones, seeds, bootstrap, limpieza
├── seeds/                  # products.yaml (catálogo inicial)
├── docs/                   # Specs, manuales, diagramas
├── evaluation/             # golden_set.yaml para eval del grafo
├── docker-compose.yml      # 3 servicios (sin Postgres)
└── .env.example            # Plantilla de variables
```

### Servicio `agent` (puerto 8001)

**Responsabilidades:**
- Recibir webhooks de WhatsApp (verificación + mensajes).
- Ejecutar el grafo LangGraph para cada mensaje autorizado.
- Persistir conversaciones, mensajes, decisiones y tickets.
- Enviar respuestas por Graph API.
- Endpoint interno de playground.

**Capas internas (convención Clean Architecture):**
- `app/api/` — routers FastAPI (`whatsapp_router`, `playground_router`, `health`).
- `app/agent/` — orquestador + grafo + nodos.
- `app/integrations/` — cliente WhatsApp.
- `app/db/` — repositorios específicos del agente (si los hay; la mayoría vive en common).

**Entrypoint:** `services/agent/src/app/main.py`

### Servicio `backoffice-api` (puerto 8002)

**Responsabilidades:**
- Autenticación JWT (login, roles).
- CRUD de documentos, productos, RTCs, prompts, tickets, config agente.
- Pipeline ETL (Docling + chunking + embeddings).
- Analytics agregadas.
- Proxy al playground del agente.

**Extra de dependencias:** `[etl]` incluye `docling>=2.0` para conversión PDF.

**Entrypoint:** `services/backoffice-api/src/app/main.py`  
**Swagger:** `http://localhost:8002/docs`

### Servicio `backoffice-web` (puerto 3000)

**Responsabilidades:**
- UI del backoffice con App Router de Next.js.
- Server Actions / SSR que llaman a backoffice-api.
- Cookie httpOnly `biomont_session` con JWT.

**Rutas principales:** ver sección [Backoffice](#11-backoffice-api--web).

### Convenciones del repositorio

Reglas en `.cursor/rules/`:
- Arquitectura limpia FastAPI (api → services → db/adapters).
- `snake_case` / `PascalCase` / `UPPER_SNAKE_CASE`.
- Tests obligatorios para cambios funcionales (mocks, sin I/O externo real en CI).
- Logging structlog JSON.
- Sin dependencias triviales; sin SQL disperso en handlers.

---

## 5. Base de datos PostgreSQL

### Infraestructura

- **Hosting:** Railway (cloud), **no** incluido en docker-compose local.
- **Conexión:** `DATABASE_URL` en todos los servicios Python.
- **Migraciones:** scripts SQL en `migrations/`, aplicados con `railway run ./scripts/apply_migration.sh NNN`.

### Extensiones PostgreSQL

| Extensión | Uso |
|-----------|-----|
| `vector` (pgvector) | Embeddings en `knowledge_chunks` (HNSW cosine) |
| `pgcrypto` | UUIDs, hashes |
| `pg_trgm` | Similitud trigram en aliases de productos y resolución |
| `unaccent` | Normalización de texto (aliases, búsqueda) |

### Migraciones

| # | Archivo | Contenido |
|---|---------|-----------|
| 001 | `001_extensions_and_core.sql` | Países, RBAC backoffice, RTCs |
| 002 | `002_rag.sql` | `documents`, `document_chunks` (legacy, eliminada en 007) |
| 003 | `003_conversations_tickets.sql` | System prompts, conversaciones, decisiones, tickets |
| 004 | `004_knowledge_restructure.sql` | Productos, aliases, secciones, `knowledge_chunks`, `conversation_state` |
| 006 | `006_product_document_links.sql` | Tabla puente `document_products` (N:M) |
| 007 | `007_drop_faq_and_legacy_chunks.sql` | Elimina `faq_entries`, `document_chunks` |
| 008 | `008_agent_config_from_backoffice.sql` | Config versionada del agente |

> Nota: no existe migración 005 numerada en el repositorio actual.

### Tablas principales (estado actual)

#### RBAC y usuarios backoffice

```sql
-- Roles: admin | scientist | viewer
bo_users (id, email, password_hash, role, ...)
bo_audit_log (entity, action, before/after JSONB, ...)

countries (iso2 PK)  -- PE, BO, EC, CO, CL, MX, AR
```

#### RTCs (usuarios WhatsApp)

```sql
rtc_users (
  id, phone_e164 UNIQUE, enabled boolean,
  display_name, created_at, ...
)
rtc_user_countries (rtc_user_id, country_iso)  -- PK compuesta
```

#### Catálogo de productos

```sql
products (
  id, name, brand DEFAULT 'Biomont',
  duration_type, description,
  country_iso NULLABLE,  -- NULL = global
  UNIQUE (lower(name), COALESCE(country_iso, 'XX'))
)

product_aliases (
  id, product_id FK,
  alias text,
  normalized_alias GENERATED (immutable_unaccent_lower),
  source IN ('name', 'manual', 'bootstrap'),
  confidence numeric(3,2)
)
-- Índice GIN trigram sobre normalized_alias
```

#### Documentos y conocimiento RAG

```sql
-- Enum document_kind: ficha_tecnica | bitacora | balotario
-- Enum document_status: draft | processing | validated | archived | failed

documents (
  id, title, kind, status,
  markdown text,           -- transcripción Docling
  content_sha256,        -- deduplicación idempotente
  country_iso, language,
  product_id FK NULLABLE,  -- FK legacy/directa
  product_name text,       -- campo legacy
  classification jsonb,    -- metadata ETL
  ...
)

document_sections (
  id, document_id FK,
  section_index, parent_section_id,
  section_number, section_title, section_kind,
  page_start, page_end, raw_text
)

knowledge_chunks (
  id, document_id FK, section_id FK,
  product_id FK NULLABLE,
  kind document_kind,
  section_type, subsection_type, topic,
  content text, token_count,
  contains_table bool, contains_dose bool,
  species text[],
  metadata jsonb,
  embedding vector(1536),
  tsv tsvector GENERATED,  -- BM25 español
  ...
)
-- Índices: HNSW(cosine) en embedding, GIN en tsv

document_products (
  document_id, product_id,
  is_primary bool
)  -- relación N:M documento ↔ producto
```

#### Conversaciones y agente

```sql
system_prompts (
  version int UNIQUE, content text,
  is_active bool  -- solo una activa
)

conversations (id, rtc_user_id FK, ...)

messages (
  id, conversation_id FK,
  role IN ('user', 'assistant', 'system'),
  content text,
  citations jsonb,
  latency_ms
)

agent_decisions (
  id, message_id FK,
  decision IN ('answered', 'low_confidence', 'no_match', 'blocked', 'error'),
  reasoning text,
  retrieved jsonb,       -- chunks recuperados
  top_similarity float,  -- score fusionado del top-1
  system_prompt_version int,
  graph_trace jsonb      -- traza de nodos LangGraph
)

conversation_state (
  conversation_id PK FK,
  current_product_id FK NULLABLE,
  current_topic, current_species, last_intent,
  updated_at
)  -- memoria determinista 1:1 con conversación

tickets (
  id, conversation_id FK, message_id FK,
  type IN ('no_info', 'low_confidence', 'user_request'),
  status IN ('open', 'in_progress', 'resolved', 'wont_fix'),
  summary, notes, ...
)
```

#### Configuración del agente (spec 008)

```sql
agent_config_versions (
  id, version UNIQUE, is_active,
  top_k, candidate_k,
  full_corpus_for_all_intents bool,
  classifier_preamble text,
  created_by FK bo_users
)

agent_intent_config (
  id, config_version_id FK,
  intent_slug,           -- enum Intent
  display_label,
  classifier_hint,       -- texto para prompt del clasificador
  document_kinds text[], -- filtro MetaFilter
  sort_order, is_enabled
)
```

### Enums importantes

**`document_kind`:** `ficha_tecnica`, `bitacora`, `balotario`

**`Intent` (código Python, sincronizado con config DB):**
- `dosage_question`
- `clinical_protocol`
- `comparison_with_competitor`
- `safety_question`
- `chitchat`
- `out_of_scope`

**`agent_decisions.decision`:**
- `answered` — respuesta con citas válidas
- `low_confidence` — ambigüedad de producto o citas faltantes
- `no_match` — retrieval débil, sin evidencia
- `blocked` — teléfono no autorizado
- `error` — fallo interno

---

## 6. ETL e ingestión de documentos

### Pipeline completo

```
PDF (bytes)
  │
  ▼
Docling (PdfToMarkdownConverter)
  │  → markdown estructurado
  ▼
StructuredMarkdownChunker (por DocumentKind)
  │  → detecta secciones numeradas
  │  → genera chunks con metadata enriquecida
  ▼
OpenAI Embeddings (batch)
  │  → vector(1536) por chunk
  ▼
Transacción Postgres:
  ├── INSERT document_sections
  ├── INSERT knowledge_chunks (+ tsv auto-generado)
  └── UPDATE documents.status = 'validated'
```

**Archivo principal:** `services/backoffice-api/src/app/services/etl_pipeline.py`

### Docling

- Librería: [docling-project/docling](https://github.com/docling-project/docling)
- Convierte PDF → markdown preservando estructura.
- Singleton por proceso para evitar cold-start repetido.
- Solo disponible con extra `[etl]` en backoffice-api.

### Chunking estructural (`StructuredMarkdownChunker`)

**Archivo:** `services/common/src/biomont_common/integrations/text_splitter.py`

Detecta cabeceras según tipo de documento:

| Kind | Patrones de sección |
|------|---------------------|
| `ficha_tecnica` | `^\d+\.\s+[A-ZÁÉÍÓÚÑ ]+$` (ej. "1. COMPOSICIÓN") |
| `bitacora` | `^\d+°\s+`, `^\d+\.\d+\s+` |
| `balotario` | `^•\s+¿.+\?$` (preguntas tipo FAQ) |

**Parámetros (env):**
- `RAG_KNOWLEDGE_CHUNK_TOKENS` — default 1000 tokens por chunk
- `RAG_KNOWLEDGE_CHUNK_OVERLAP` — default 120 tokens de solapamiento

**Metadata enriquecida por chunk:**
- `section_type`, `subsection_type`, `topic`
- `contains_dose` — detecta patrones `mg/kg`, `mg`, frecuencias
- `contains_table` — detecta tablas de dosificación
- `species[]` — especies mencionadas (best-effort)

**Fallo explícito:** si no se detectan secciones esperadas → documento queda `failed` con razón `etl_no_sections_detected`.

### Upload de documentos

**Endpoint:** `POST /documents` (multipart/form-data)

**Campos:**
- `file` — PDF
- `title`, `kind` (ficha_tecnica | bitacora | balotario)
- `country_iso`, `language`
- `product_id` — FK directa (opcional)
- `product_ids[]` — enlaces N:M vía `document_products`
- `product_name` — legacy

**Roles permitidos:** `admin`, `scientist`

**Auto-match de producto:** si similitud trigram ≥ 0.95 con un producto existente, se asocia automáticamente.

### Idempotencia y deduplicación

- Hash SHA-256 del contenido (`content_sha256`) evita re-ingestar duplicados exactos.
- Reingesta explícita: `POST /documents/{id}/reingest` (solo `admin`) — borra secciones/chunks y reprocesa.

### Bootstrap de productos

**Script:** `scripts/bootstrap_products.py`  
**Seed:** `seeds/products.yaml`

Crea/actualiza productos y aliases de forma idempotente. Ejemplo de aliases para Proteggo 3M: "proteggo 3m", "el verde", "el de 3 meses", "trimestral", etc.

### Calibración de regex ETL

Documentación de patrones en `docs/etl-regex-calibration/` — análisis de PDFs reales de Biomont para afinar detección de secciones.

### Evolución: eliminación del atajo FAQ (spec 007)

Anteriormente existía:
- Tabla `faq_entries` con extractor LLM del balotario.
- Nodo `FAQRetriever` que respondía directo sin pasar por Answerer.

**Estado actual:** eliminado. El balotario se chunkifica como cualquier documento y el retrieval híbrido + Answerer responde las preguntas FAQ. Esto simplifica el pipeline y unifica la auditoría.

---

## 7. Corpus documental y RAG

### Modelo de conocimiento

- **Unidad de retrieval:** `knowledge_chunks` (no el markdown completo del documento).
- **Granularidad:** chunks de ~1000 tokens con overlap, anclados a secciones del PDF.
- **Índice vectorial:** HNSW con `vector_cosine_ops` en embedding(1536).
- **Índice léxico:** `tsv tsvector` generado con `to_tsvector('spanish', content)` para BM25.

### Retrieval híbrido

**Archivo SQL centralizado:** `services/common/src/biomont_common/db/rag_repository.py`

**Fórmula de fusión:**
```
vec_score  = 1 - (embedding <=> query_embedding)     -- distancia coseno
bm25_score = ts_rank_cd(tsv, plainto_tsquery('spanish', query))
final_score = vector_weight * normalize(vec) + bm25_weight * normalize(bm25)
```

**Defaults:**
- `RAG_VECTOR_WEIGHT = 0.7`
- `RAG_BM25_WEIGHT = 0.3`
- `RAG_TOP_K = 6` (chunks finales)
- `RAG_CANDIDATE_K = 25` (candidatos por canal antes de fusionar)

La normalización es min-max sobre el conjunto candidato del CTE.

### Filtros pre-retrieval (MetaFilter)

Antes de calcular scores, el SQL filtra por:

1. **`documents.status = 'validated'`** — solo documentos aprobados.
2. **País del RTC** — `country_iso IN (allowed) OR country_iso IS NULL`.
3. **`product_id` resuelto** — incluye match vía `document_products` (N:M).
4. **`document_kind[]`** — según intent clasificado (configurable desde backoffice).

**Mapa default de intent → kinds** (cuando `full_corpus_for_all_intents = false`):

| Intent | document_kind[] |
|--------|-----------------|
| `clinical_protocol` | bitacora, balotario |
| `dosage_question` | bitacora, ficha_tecnica, balotario |
| `safety_question` | ficha_tecnica, bitacora, balotario |
| `comparison_with_competitor` | bitacora |
| resto | sin filtro (null) |

Si `full_corpus_for_all_intents = true` (flag QA), se ignoran filtros por kind.

### Gate de similitud (orquestador)

El orquestador compara `top_similarity` (score fusionado del chunk top-1) contra un umbral:

```python
gate = min(AGENT_SIMILARITY_THRESHOLD, RAG_VECTOR_WEIGHT)
# default: min(0.75, 0.7) = 0.7
```

Si `top_similarity < gate` → decisión `no_match` + ticket `no_info`.

### Respuesta con citaciones

El nodo **Answerer** llama al LLM con `with_structured_output(RagAnswer)`:

```python
class RagAnswer:
    answer: str
    citations: list[Citation]  # document_id, chunk_id, title, similarity
```

Si el LLM no produce citaciones válidas → `low_confidence` + ticket.

**Formato al RTC:** bloque "Fuentes:" con títulos de documentos (no expone scores internos al usuario final en el mensaje principal; los scores se persisten en `agent_decisions` para auditoría).

---

## 8. Agente conversacional

### Orquestador

**Archivo:** `services/agent/src/app/agent/orchestrator.py`

**Flujo por mensaje:**

1. Validar RTC (WhatsApp por teléfono, playground por ID).
2. `get_or_create_active_conversation(rtc_user_id)`.
3. Insertar mensaje usuario en `messages`.
4. Cargar system prompt activo de `system_prompts` (caché TTL 60s).
5. Leer `current_product_id` de `conversation_state` (herencia).
6. Ejecutar grafo LangGraph.
7. Decidir respuesta según reglas de negocio (ver abajo).
8. Opcional: mensaje de confirmación de producto.
9. Persistir mensaje assistant + `agent_decisions` con `graph_trace`.
10. Enviar por WhatsApp (hasta 2 mensajes si hay confirmación).

### Grafo LangGraph

**Archivo:** `services/agent/src/app/agent/graph/graph.py`

```
START
  │
  ▼
IntentClassifier
  │
  ▼
ProductResolver ──(ambiguous)──► END (repregunta producto)
  │
  (ok)
  ▼
MetaFilter
  │
  ▼
HybridRetriever
  │
  ▼
Answerer
  │
  ▼
StateUpdater
  │
  ▼
END
```

### Nodos del grafo

| Nodo | Archivo | Determinístico | Función |
|------|---------|----------------|---------|
| IntentClassifier | `nodes/intent_classifier.py` | No (LLM) | Clasifica intent con structured output |
| ProductResolver | `nodes/product_resolver.py` | **Sí** | Match exacto + pg_trgm; herencia de estado |
| MetaFilter | `nodes/meta_filter.py` | **Sí** | Mapea intent → document_kind[] |
| HybridRetriever | `nodes/hybrid_retriever.py` | **Sí** | Embedding query + SQL híbrido |
| Answerer | `nodes/answerer.py` | No (LLM) | Genera respuesta con citaciones |
| StateUpdater | `nodes/state_updater.py` | **Sí** | Upsert conversation_state |
| Calculator | `nodes/calculator.py` | — | **Placeholder** (NotImplementedError, no enrutado) |

### IntentClassifier

- Modelo: `gpt-4o-mini`, temperature 0, structured output JSON.
- Prompt ensamblado desde `agent_config_versions.classifier_preamble` + hints por intent de `agent_intent_config`.
- Caché por hash de mensaje + namespace de config activa.
- Calibración léxica adicional para `safety_question` (efectos adversos, gestación, lactancia, etc.).

### ProductResolver

Estrategia (sin LLM):

1. Match exacto en `product_aliases.normalized_alias`.
2. Si no: `pg_trgm.similarity()` sobre aliases, LIMIT 5.
3. Si top-1 ≥ `PRODUCT_RESOLVER_THRESHOLD` (0.55) **y** margen top-1 − top-2 ≥ `PRODUCT_RESOLVER_MARGIN` (0.10) → resuelto.
4. Si no hay mención de producto pero existe `current_product_id` en `conversation_state` → heredar con `inherited_from_state=true`.
5. Si ambiguo → lista de candidatos → orquestador repregunta sin llamar Answerer.

**Mensaje de ambigüedad:**
> "Para responder bien necesito que me confirmes el producto. Estoy entre: {A} / {B} / {C}. ¿Cuál te interesa?"

### StateUpdater (memoria conversacional)

Persiste en `conversation_state`:
- `current_product_id` — producto resuelto o heredado
- `current_topic` — intent del turno
- `current_species` — extraído por regex (best-effort, puede ser NULL)
- `last_intent` — slug del intent

Permite follow-ups como "¿Y en lactancia?" sin re-mencionar el producto.

### Decisiones del orquestador

| Condición | decision | Respuesta al RTC | Ticket |
|-----------|----------|------------------|--------|
| Teléfono no en rtc_users o disabled | `blocked` | "No estás autorizado..." | No |
| Producto ambiguo | `low_confidence` | Repregunta producto | No |
| top_similarity < gate o sin chunks | `no_match` | "No tengo esa información..." | `no_info` |
| Answer sin citaciones | `low_confidence` | "No tengo información con suficiente confianza..." | `low_confidence` |
| Answer con citaciones | `answered` | Respuesta + Fuentes | No |

**Confirmación de producto (answered):**
- Producto nuevo resuelto: "Para esta respuesta tomé como referencia el producto *{nombre}*."
- Producto heredado: "Para esta respuesta sigo usando la información del producto *{nombre}*."

### System prompt vs config del agente

Son dos configuraciones distintas:

| Config | Tabla | Consumidor | Qué controla |
|--------|-------|------------|--------------|
| System prompt | `system_prompts` | Answerer | Tono, reglas de citación, abstención |
| Agent config | `agent_config_versions` + `agent_intent_config` | IntentClassifier, MetaFilter, HybridRetriever | top_k, intents, kinds, preamble clasificador |

**System prompt seed (v1):**
> Eres el asistente de productos veterinarios de Biomont. Solo respondes con información presente en los documentos validados... No inventar. Citar siempre el documento. Responder en el idioma del usuario.

### Evaluación automatizada

**Golden set:** `evaluation/golden_set.yaml`

Casos de prueba con expectativas de intent, producto, kinds filtrados, decision y substrings en respuesta.

**Tests:** `services/agent/tests/test_golden_set_eval.py` (marcados `@pytest.mark eval`, requieren DB con datos reales).

---

## 9. Tipos de preguntas y comportamiento esperado

### Taxonomía de intents y ejemplos

| Intent | Descripción | Ejemplos de preguntas | Documentos preferidos |
|--------|-------------|----------------------|----------------------|
| `dosage_question` | Dosis, indicaciones, posología | "¿Qué dosis de Proteggo 3M le doy a un perro de 25 kg?", "¿Cuál es la indicación de Imperia?" | bitacora, ficha_tecnica, balotario |
| `clinical_protocol` | Protocolos de tratamiento, esquemas | "¿Cuál es el protocolo para DAPP?" | bitacora, balotario |
| `safety_question` | Seguridad, gestación, lactancia, contraindicaciones, efectos adversos | "¿Puede usarse en gestación?", "¿Contraindicaciones en gatos?" | ficha_tecnica, bitacora, balotario |
| `comparison_with_competitor` | Comparativas con competencia | "¿Cómo se compara con Bravecto?" | bitacora |
| `chitchat` | Saludos, cortesía | "Hola", "Gracias" | Sin filtro especial |
| `out_of_scope` | Fuera del dominio veterinario/Biomont | "¿Cuál es la capital de Francia?" | Sin retrieval útil → no_match |

### Casos de prueba operativos (RTC)

De `docs/guia-pruebas-rtc.md`:

| # | Tipo | Pregunta ejemplo | Resultado esperado |
|---|------|------------------|-------------------|
| 1 | Autorización | "Hola, quiero consultar sobre un producto" | Respuesta normal (no "no autorizado") |
| 2 | FAQ / balotario | "¿Puede usarse en gestación?" | Respuesta + referencia documental |
| 3 | Dosis | "¿Qué dosis de [producto] le doy a un perro de 25 kg?" | Dosis mg/kg + cita |
| 4 | Protocolo | "¿Cuál es el protocolo para DAPP?" | Respuesta bitácora + cita |
| 5 | Ambigüedad | "¿Cuánto cuesta el Proteggo?" | Repregunta o baja confianza |
| 6 | Fuera de alcance | "¿Cuál es la capital de Francia?" | Abstención, no inventa |
| 7 | Seguimiento | Tras dosis: "¿Y en lactancia?" | Mantiene producto del hilo |

### Limitaciones actuales del agente

1. **Solo mensajes de texto** — no procesa imágenes, audios ni documentos adjuntos.
2. **No calcula dosis automáticamente** — el nodo Calculator está como placeholder; responde con texto de documentos, no con motor de cálculo estructurado.
3. **No responde precios comerciales** — preguntas de precio sobre productos ambiguos generan repregunta o abstención.
4. **No accede a internet** — solo corpus indexado en Postgres.
5. **Un tenant** — no hay multi-empresa; config es global.

### Qué NO debe hacer el agente

- Inventar dosis, contraindicaciones o protocolos.
- Responder sin citar fuente documental.
- Responder a teléfonos no registrados.
- Mezclar información de productos homónimos sin confirmación.
- Revelar el system prompt o metadatos internos al RTC.

---

## 10. Canal WhatsApp e integración Meta

### Endpoints del agente

| Método | Ruta | Función |
|--------|------|---------|
| GET | `/whatsapp/webhook` | Verificación Meta (`hub.mode`, `hub.verify_token`, `hub.challenge`) |
| POST | `/whatsapp/webhook` | Recepción de mensajes |

### Seguridad webhook

- **GET:** valida `hub.verify_token` contra `WHATSAPP_VERIFY_TOKEN`.
- **POST:** valida HMAC-SHA256 del body con `WHATSAPP_APP_SECRET` en header `X-Hub-Signature-256`.

### Cliente Graph API

**Archivo:** `services/agent/src/app/integrations/whatsapp_client.py`

- Versión: `WHATSAPP_GRAPH_API_VERSION` (default `v20.0`).
- Envío: `POST /{phone_number_id}/messages` con `messaging_product: whatsapp`.
- Solo mensajes de **texto** salientes.

### Configuración en Meta Developer Console

- **Callback URL:** `https://<dominio-agente>/whatsapp/webhook`
- **Verify token:** valor de `WHATSAPP_VERIFY_TOKEN`
- **Suscripción:** campo `messages`
- **Desarrollo local:** `ngrok http 8001` para exponer webhook

### Normalización de teléfonos

Los RTCs se registran en formato **E.164** (ej. `+51987654321`) en `rtc_users.phone_e164`.

---

## 11. Backoffice (API + Web)

### Roles y permisos (RBAC)

| Rol | Permisos |
|-----|----------|
| `viewer` | Lectura: conversaciones, documentos, decisiones, tickets, analytics |
| `scientist` | + Upload documentos, CRUD productos/aliases, playground |
| `admin` | + Delete productos, reingest documentos, activar prompts/config |

Autenticación: JWT en cookie httpOnly `biomont_session`, emitido por `POST /auth/login`.

### Navegación web

| Ruta | Función |
|------|---------|
| `/login` | Autenticación |
| `/dashboard` | Analytics overview |
| `/conversations` | Espejo de chats + playground |
| `/documents` | Catálogo + upload PDF |
| `/documents/[id]` | Detalle: markdown, secciones, chunks, productos |
| `/products` | CRUD productos + aliases |
| `/products/[id]` | Detalle producto |
| `/agent-decisions` | Auditoría decisiones IA |
| `/agent-decisions/[id]` | Detalle enriquecido (BFF spec 010) |
| `/rtcs` | CRUD RTCs WhatsApp |
| `/prompts` | System prompt versionado |
| `/agent-config` | Config retrieval + intents |
| `/tickets` | Gestión tickets del agente |

### API REST — endpoints principales

Base: `http://localhost:8002` (prod: dominio Railway)

| Prefijo | Endpoints |
|---------|-----------|
| `/health` | GET healthcheck |
| `/auth/login`, `/auth/me` | Autenticación |
| `/documents` | GET list, POST upload, DELETE, PATCH |
| `/documents/{id}/reingest` | POST reingesta (admin) |
| `/documents/{id}/sections` | GET secciones |
| `/documents/{id}/knowledge-chunks` | GET chunks paginados |
| `/documents/{id}/products` | GET/PATCH enlaces N:M |
| `/products` | CRUD + aliases |
| `/rtcs` | CRUD RTCs |
| `/conversations` | GET list + detalle con mensajes |
| `/playground/messages` | POST proxy al agente |
| `/system-prompts` | GET, POST nueva versión, POST activate |
| `/agent-config/versions` | GET, POST create, POST activate |
| `/agent-config/active` | GET config activa |
| `/agent-decisions` | GET list filtrable |
| `/agent-decisions/{id}` | GET detalle enriquecido |
| `/tickets` | GET list, PATCH update |
| `/analytics/overview` | GET métricas agregadas |

### Analytics (dashboard)

Métricas en overview:
- Total conversaciones, mensajes, answered vs no_match
- Latencia media del assistant
- Uso por país (desde documentos citados)
- Top 10 productos consultados

### Playground

Permite simular conversaciones seleccionando un RTC habilitado. Útil para QA sin enviar WhatsApp real. Requiere roles `admin` o `scientist`.

**Secreto compartido:** `AGENT_PLAYGROUND_SECRET` debe coincidir en agent y backoffice-api.

---

## 12. Configuración, variables de entorno y parámetros

### Variables críticas

#### Postgres (todos los servicios Python)
```
DATABASE_URL=postgres://...
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=10
DB_STATEMENT_TIMEOUT_MS=30000
```

#### OpenAI
```
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_EMBEDDINGS_MODEL=text-embedding-3-small
OPENAI_EMBEDDINGS_DIM=1536
```
> Cambiar `OPENAI_EMBEDDINGS_DIM` o modelo de embeddings requiere **reingesta total** de todos los documentos.

#### WhatsApp (solo agent)
```
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_APP_SECRET=
WHATSAPP_GRAPH_API_VERSION=v20.0
```

#### Agente / RAG
```
AGENT_SIMILARITY_THRESHOLD=0.75
AGENT_TOP_K=6
AGENT_SYSTEM_PROMPT_CACHE_TTL_SECONDS=60
AGENT_PLAYGROUND_SECRET=
RAG_VECTOR_WEIGHT=0.7
RAG_BM25_WEIGHT=0.3
RAG_TOP_K=6
RAG_CANDIDATE_K=25
RAG_FULL_CORPUS_FOR_ALL_INTENTS=false
PRODUCT_RESOLVER_THRESHOLD=0.55
PRODUCT_RESOLVER_MARGIN=0.10
RAG_KNOWLEDGE_CHUNK_TOKENS=1000
RAG_KNOWLEDGE_CHUNK_OVERLAP=120
```

#### Backoffice
```
JWT_SECRET=          # >= 32 chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=480
BACKOFFICE_API_CORS_ORIGINS=http://localhost:3000
AGENT_INTERNAL_BASE_URL=http://agent:8001
NEXT_PUBLIC_API_BASE_URL=http://localhost:8002
API_INTERNAL_BASE_URL=http://backoffice-api:8002
SESSION_COOKIE_SECURE=false   # true en prod HTTPS
```

#### Logging
```
LOG_LEVEL=INFO
LOG_JSON=true
```

### Precedencia de configuración del agente

1. **Config activa en DB** (`agent_config_versions` + `agent_intent_config`) — top_k, candidate_k, intents, kinds, preamble.
2. **Variables de entorno** — fallback si no hay config DB o para pesos híbridos (vector/bm25).
3. **Hardcode** — solo para enum Intent y lógica estructural del grafo.

---

## 13. Despliegue e infraestructura

### Docker Compose (desarrollo local)

```bash
docker compose up --build
```

- 3 servicios en red `biomont-network`.
- Postgres **externo** (Railway) vía `DATABASE_URL`.
- Healthchecks en `/health`.
- `backoffice-api` depende de `agent` healthy.

### Railway (producción)

Cada servicio tiene `railway.toml` con `watchPatterns` independientes.

**Build context:** raíz del repo (Dockerfiles copian `services/common`).

**Variables prod críticas:**
- `AGENT_INTERNAL_BASE_URL=https://${{agent.RAILWAY_PUBLIC_DOMAIN}}` en backoffice-api
- `AGENT_PLAYGROUND_SECRET` idéntico en agent y backoffice-api
- `DATABASE_URL` desde plugin Postgres Railway
- `SESSION_COOKIE_SECURE=true`

### Scripts operativos

| Script | Función |
|--------|---------|
| `scripts/apply_migration.sh NNN` | Aplicar migración |
| `scripts/seed_dev.sql` | System prompt v1 |
| `scripts/seed_admin.sh email pass` | Crear admin backoffice (argon2) |
| `scripts/bootstrap_products.py` | Catálogo productos desde YAML |
| `scripts/clean_test_data.sh` | Limpiar datos de prueba |
| `scripts/railway_psql.sh` | Helper psql Railway |

### Bootstrap completo (primera vez)

```bash
cp .env.example .env
railway link
railway run ./scripts/apply_migration.sh 001
# ... hasta 008
railway run psql -f scripts/seed_dev.sql
railway run ./scripts/seed_admin.sh admin@example.com 'password'
DATABASE_URL=... python scripts/bootstrap_products.py
docker compose up --build
```

---

## 14. Observabilidad, auditoría y debugging

### Logging

- **Formato:** structlog JSON (`LOG_JSON=true`).
- **Eventos clave del agente:**
  - `agent_blocked` — teléfono no autorizado
  - `agent_decision` — decisión final con top_similarity, latency_ms, ticket_id
  - `node_started` / `node_completed` — por nodo del grafo
- **Regla:** logs no vuelcan contenido completo de chunks (truncado).

### Auditoría en base de datos

| Tabla | Qué audita |
|-------|------------|
| `agent_decisions` | Cada turno: decision, retrieved chunks, top_similarity, graph_trace |
| `bo_audit_log` | Mutaciones backoffice (activate prompt, config, etc.) |
| `tickets` | Gaps de conocimiento detectados por el agente |
| `messages` | Transcript completo con citations JSONB |

### graph_trace

Campo JSONB en `agent_decisions` con lista ordenada de nodos:

```json
[
  {"node": "IntentClassifier", "latency_ms": 850, "outcome": "classified", "payload": {"intent": "dosage_question"}},
  {"node": "ProductResolver", "latency_ms": 45, "outcome": "resolved", "payload": {"product_id": "..."}},
  {"node": "MetaFilter", "latency_ms": 1, "outcome": "filtered", "payload": {"kinds": ["bitacora", "ficha_tecnica"]}},
  {"node": "HybridRetriever", "latency_ms": 320, "outcome": "retrieved", "payload": {"count": 6}},
  {"node": "Answerer", "latency_ms": 4200, "outcome": "answered"},
  {"node": "StateUpdater", "latency_ms": 12, "outcome": "updated"}
]
```

### Troubleshooting común

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| "No estás autorizado" | Teléfono no en rtc_users o disabled | Alta en backoffice `/rtcs` |
| "No tengo esa info" siempre | Sin docs validated, sin embeddings, país incorrecto | Verificar documentos, reingestar, países RTC |
| Webhook 401 invalid signature | WHATSAPP_APP_SECRET incorrecto | Verificar en Meta Developer Console |
| extension "vector" does not exist | Plan Railway sin pgvector | Upgrade plan Postgres Railway |
| Producto equivocado | Aliases insuficientes o ambigüedad | Agregar aliases, mejorar repregunta |
| Respuesta lenta (>15s) | LLM + retrieval | Revisar top_k, latencia OpenAI |

### Debug por teléfono RTC

Skill operativa: `.cursor/skills/review-conversations-by-phone/SKILL.md` — SQL para revisar hilos por `rtc_users.phone_e164`.

### Debug local Docker

Skill: `.cursor/skills/review-docker-compose-local/SKILL.md` — logs por servicio.

---

## 15. Evolución del proyecto (historial de specs)

| Spec | Título | Estado | Impacto |
|------|--------|--------|---------|
| 001 | Foundation v1 | Base | Pipeline LCEL inicial, document_chunks, webhook WhatsApp |
| 002 | Conversaciones espejo + playground | Implementada | Mirror de chats en backoffice, playground interno |
| 003 | LangGraph + RAG híbrido + reestructuración | Implementada | Grafo, knowledge_chunks, productos, FAQ shortcut, conversation_state |
| 004 | Productos, documentos, agent-decisions | Implementada | CRUD productos, UI documentos, auditoría decisiones |
| 005 | Feedback async + loading states | Implementada | UX backoffice con estados de carga |
| 006 | Vínculo producto↔documento N:M | Implementada | document_products |
| 007 | Eliminar FAQ shortcut e ingest legacy | Implementada | DROP faq_entries, document_chunks; flujo unificado |
| 008 | Config agente en DB | Implementada | agent_config_versions, editable desde backoffice |
| 009 | UX catálogo: búsqueda, formularios | Implementada | Mejoras UI catálogo |
| 010 | Decisiones: BFF enrichment | Implementada | Detalle enriquecido de decisiones con preview chunks |

### Línea de tiempo arquitectónica

1. **v1:** Pipeline LCEL lineal → `document_chunks` → retrieval solo vectorial.
2. **spec 003:** LangGraph + híbrido vec+BM25 + productos + FAQ directo.
3. **spec 007:** Eliminación FAQ shortcut → un solo camino híbrido+LLM.
4. **spec 008:** Config operativa editable sin redeploy.

---

## 16. Fuera de alcance y roadmap

### Fuera de alcance actual

- Almacenamiento de PDFs originales en bucket (solo markdown en DB).
- Motor de cálculo de dosis estructurado (nodo Calculator placeholder).
- Tablas clínicas estructuradas (protocols, parasites, competitors, etc.).
- Reranker con cross-encoder.
- Resumidor LLM de conversación (memoria es determinista).
- Migración a embeddings `text-embedding-3-large`.
- Config por RTC o por país (config es global).
- Multi-tenant / multi-laboratorio.
- Procesamiento de imágenes, audio, documentos adjuntos en WhatsApp.
- Integración con ERP/CRM de Biomont.

### Roadmap implícito (mencionado en specs)

- **Calculator node:** motor de dosis con fórmulas/tablas estructuradas.
- **Fase 2 schema clínico:** protocols, product_indications, competitive_arguments.
- **Reranker:** cross-encoder opcional post-retrieval.
- **Pesos híbridos editables** desde backoffice (hoy solo env).
- **Intents dinámicos** fuera del enum actual.

---

## 17. Glosario

| Término | Defición |
|---------|----------|
| **RTC** | Representante Técnico Comercial — usuario final del agente WhatsApp |
| **RAG** | Retrieval-Augmented Generation — generación aumentada con recuperación de documentos |
| **Chunk** | Fragmento de texto indexado con embedding para retrieval |
| **Kind** | Tipo de documento: ficha_tecnica, bitacora, balotario |
| **Intent** | Clasificación de la intención del mensaje del usuario |
| **Gate** | Umbral mínimo de similitud para aceptar una respuesta |
| **Playground** | Simulador interno de conversaciones sin WhatsApp |
| **ETL** | Extract-Transform-Load — pipeline PDF → markdown → chunks → embeddings |
| **BFF** | Backend For Frontend — endpoint enriquecido para la UI |
| **Golden set** | Conjunto de casos de prueba con expectativas para evaluación del grafo |
| **HNSW** | Hierarchical Navigable Small World — índice aproximado para búsqueda vectorial |
| **BM25** | Best Matching 25 — ranking léxico full-text |
| **E.164** | Formato internacional de teléfono (+51987654321) |

---

## 18. Mapa de archivos clave

### Documentación

| Archivo | Contenido |
|---------|-----------|
| `README.md` | Bootstrap, stack, troubleshooting |
| `requerimentos-proyecto.md` | Requisitos originales del cliente |
| `docs/specs/README.md` | Índice de specs |
| `docs/guia-pruebas-rtc.md` | Guía operativa para RTC |
| `docs/manual-usuario-backoffice.md` | Manual backoffice |
| `docs/architecture-biomont.mmd` | Diagrama arquitectura |
| `docs/flow-rtc-y-backoffice.mmd` | Flujos RTC y backoffice |

### Agente

| Archivo | Contenido |
|---------|-----------|
| `services/agent/src/app/main.py` | Entrypoint, wiring |
| `services/agent/src/app/agent/orchestrator.py` | Caso de uso principal |
| `services/agent/src/app/agent/graph/graph.py` | Composición LangGraph |
| `services/agent/src/app/agent/graph/nodes/*.py` | Nodos del grafo |
| `services/agent/src/app/api/whatsapp_router.py` | Webhook WhatsApp |

### RAG y ETL

| Archivo | Contenido |
|---------|-----------|
| `services/common/src/biomont_common/db/rag_repository.py` | SQL retrieval híbrido |
| `services/common/src/biomont_common/integrations/text_splitter.py` | Chunkers |
| `services/backoffice-api/src/app/services/etl_pipeline.py` | Pipeline ingest |
| `services/backoffice-api/src/app/integrations/docling_converter.py` | PDF → markdown |

### Schemas y config

| Archivo | Contenido |
|---------|-----------|
| `services/common/src/biomont_common/schemas/agent_graph.py` | Enum Intent, traces |
| `services/common/src/biomont_common/schemas/rag.py` | RagAnswer, Citation |
| `services/common/src/biomont_common/settings.py` | Settings compartidos |
| `.env.example` | Variables de entorno |

### Base de datos

| Archivo | Contenido |
|---------|-----------|
| `migrations/001..008*.sql` | Schema versionado |
| `scripts/apply_migration.sh` | Aplicador migraciones |
| `seeds/products.yaml` | Catálogo productos |
| `scripts/seed_dev.sql` | System prompt inicial |

### Evaluación

| Archivo | Contenido |
|---------|-----------|
| `evaluation/golden_set.yaml` | Casos golden |
| `services/agent/tests/test_golden_set_eval.py` | Tests eval |

### Frontend

| Archivo | Contenido |
|---------|-----------|
| `services/backoffice-web/lib/api.ts` | Cliente API |
| `services/backoffice-web/components/dashboard-nav.tsx` | Navegación |
| `services/backoffice-web/app/(dashboard)/` | Páginas dashboard |

---

## Apéndice A — Preguntas frecuentes técnicas (FAQ para IA)

**¿Dónde vive la base de datos?**  
PostgreSQL en Railway, fuera de docker-compose. Conexión vía `DATABASE_URL`.

**¿Cómo se evita que el agente invente respuestas?**  
Tres capas: (1) system prompt con regla de abstención, (2) gate de similitud en orquestador, (3) requisito de citaciones válidas del Answerer. Si falla cualquiera → ticket.

**¿Por qué hay dos servicios Python?**  
Separación de responsabilidades: agent (latencia, webhook) vs backoffice-api (ETL pesado con Docling, CRUD). Comparten `biomont-common`.

**¿Cómo se diferencia Proteggo M de Proteggo 3M?**  
ProductResolver con pg_trgm sobre aliases + repregunta si ambiguo. No se delega al LLM.

**¿Qué pasa si cambio el system prompt?**  
Se crea nueva versión en `system_prompts` y se activa. El agente cachea 60s.

**¿Qué pasa si subo top_k desde backoffice?**  
Nueva versión en `agent_config_versions`, activar. El agente la lee con caché TTL sin redeploy.

**¿Los PDFs se guardan?**  
No en v1. Solo markdown transcrito + chunks en Postgres.

**¿Cómo reindexar todo tras cambiar modelo de embeddings?**  
Reingestar cada documento con `POST /documents/{id}/reingest` (admin) o script batch.

**¿Cómo probar sin WhatsApp?**  
Playground en backoffice (`/conversations`) o `POST /internal/playground/messages` directo al agent.

**¿Qué migraciones debe tener prod?**  
001, 002, 003, 004, 006, 007, 008 (007 elimina tablas legacy de 002/004).

---

## Apéndice B — Contratos de datos importantes

### RagAnswer (respuesta estructurada del Answerer)

```python
class Citation(BaseModel):
    document_id: UUID
    chunk_id: UUID
    document_title: str
    similarity: float

class RagAnswer(BaseModel):
    answer: str
    citations: list[Citation]
```

### HybridChunkHit (resultado del retriever)

Incluye: chunk_id, document_id, document_title, country_iso, content, chunk_index, vec_score, bm25_score, final_score, kind, section_type, contains_dose, etc.

### HandleResult (respuesta del orquestador)

```python
decision: "answered" | "low_confidence" | "no_match" | "blocked" | "error"
reply_text: str
ticket_id: str | None
```

---

*Fin del documento. Para actualizaciones, sincronizar con el estado del repositorio y las specs en `docs/specs/`.*
