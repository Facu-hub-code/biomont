# 012 - Comparador comercial (columnas dinámicas por documento)

## Contexto y objetivo

Los RTCs preguntan comparativas frente a competencia (Bravecto, NexGard, Simparica, Atrevia, Apoquel, etc.) y también **entre productos Biomont** (Proteggo 3M vs Proteggo M, Imperia vs otros antipulgas). Hoy el intent `comparison_with_competitor` existe y filtra retrieval a `bitacora` (`agent_config_repository.py`, spec [007](./007-remove-faq-shortcut-and-legacy-ingest.md)), pero:

1. El corpus **no incluye** el Excel matricial del laboratorio (*COMPARATIVO COMERCIAL PROTEGGO 3M y M*) de forma estructurada.
2. Vectorizar la matriz completa (hoja `ESPECTRO`, 13+ columnas) degrada precisión en lookups **SI/NO**, porcentajes y seguridad en gestación.
3. La narrativa comercial (hoja `Claims`, argumentos de venta) **sí** se beneficia de RAG + citación.

**Objetivo (sprint 2):** comparador **determinista** sobre cuadros comerciales Excel (hoja `COMPARATIVO COMERCIAL`, ej. MARVO 20 / OPRURIX) con **columnas dinámicas por documento/set**. El agente nombra **diferencias sin juicio de valor**. Matriz ESPECTRO estilo Proteggo queda **fuera de alcance** de este sprint.

**Relación:** [011](./011-dose-calculation-engine.md) (mismo patrón BO: completitud, import, publicación). [003](./003-langgraph-hybrid-rag-and-knowledge-restructure.md) ADR fase 2 (`competitors`, `competitive_arguments`).

## Alcance / fuera de alcance

### En alcance

- Catálogo `competitors` (marcas externas + flag para productos Biomont usados como contraparte).
- Dimensiones de comparación (`comparison_dimensions`) y hechos (`comparison_facts`) versionados.
- Nuevo `document_kind` **`comparativo`** para PDF/markdown de claims y material comercial curado (vectorizado).
- Importador desde Excel (hojas `ESPECTRO`, `EFECTIVIDAD`, `COMPARATIVO resumen`, etc.) → borrador + gaps.
- Backoffice: hub **"Comparativa"** por producto + catálogo global de competidores + documentos `comparativo`.
- Nodo `CompetitorResolver` (match competidor mencionado) + `CompetitorLookup` (SQL) + enrutamiento con `Answerer` para síntesis citada cuando haga falta.
- Mantener `comparison_with_competitor`; ampliar `MetaFilter` para incluir `comparativo` además de `bitacora`.
- Completitud de datos comparativos por par (producto Biomont × competidor) con gaps y badge en BO (misma filosofía que [011](./011-dose-calculation-engine.md)).

### Fuera de alcance (v1)

- Comparar **más de dos** productos en una sola respuesta estructurada (v1: un subject + un competitor por turno; repregunta si faltan).
- Precios comerciales del Excel (filas con precios NexGard/Bravecto) — datos sensibles/operativos; no exponer al RTC salvo spec futura con RBAC.
- Actualización automática de datos de competencia desde internet.
- Reranker cross-encoder.
- Comparativas de productos **no antiparasitarios** (ej. tramadol Oppia vs Jhon Martin) en v1 estructurado — pueden seguir solo por RAG de bitácora/ficha hasta ampliar dimensiones.

## Estado actual (evidencia)

### Intent y retrieval

| Intent | `document_kind[]` default |
| ------ | ------------------------- |
| `comparison_with_competitor` | `bitacora` |

Sin tablas `competitors` ni `comparison_facts` en migraciones 001–008.

### Fuentes del laboratorio (Excel de referencia)

| Hoja | Contenido | Destino v1 |
| ---- | --------- | ---------- |
| `ESPECTRO` | Matriz parásito × producto (SI/NO/notas) | `comparison_facts` |
| `EFECTIVIDAD` | % eficacia pulgas/garrapatas Proteggo 3M vs M | `comparison_facts` |
| `COMPARATIVO` / `COMPARATIVO resumen` | Texto comparativo agregado | facts + opcional RAG |
| `Claims` | Bullets comerciales Proteggo 3M | documento `comparativo` vectorizado |
| `TABLETAS` | Atributos formulación (micronizado, palatabilidad) | `comparison_facts` categoría `formulation` |
| `Presentaciónes y dosis` | Presentaciones competencia | [011](./011-dose-calculation-engine.md) (dosis), no duplicar en 012 |

### Preguntas del balotario mapeadas (muestra)

| Pregunta | Modo |
| -------- | ---- |
| TC #15 Imperia+Telopar vs Simparica Trio | Híbrido (facts + narrativa) |
| TC #16 Proteggo 3M+Telopar vs Atrevia 360° | Híbrido |
| TC #7 OPRURIX vs Numelvi | RAG + facts si importados |
| Comercial #62 Proteggo 3M gestantes vs Proteggo M | **Lookup** seguridad gestación |
| Comercial #67/#68 Imperia vs otros antipulgas | RAG + facts espectro |

## Requisitos funcionales

### Modelo de datos

`Migraciones necesarias: sí` — `migrations/012_competitor_comparison.sql` (+ `.down.sql`).

- **RF-1** — Extender enum `document_kind` con valor `comparativo` (ALTER TYPE … ADD VALUE).
- **RF-2** — `competitors`:
  - `id` uuid PK
  - `name` text NOT NULL — ej. `Bravecto`, `Atrevia XR`
  - `normalized_name` text GENERATED (mismo patrón `immutable_unaccent_lower`)
  - `brand` text NULL
  - `active_principles` text NULL
  - `is_internal` boolean NOT NULL DEFAULT false — true para contrapartes Biomont (Proteggo M cuando subject es 3M)
  - `linked_product_id` uuid NULL FK → `products` — si el competidor es otro SKU Biomont
  - UNIQUE (`normalized_name`)
- **RF-3** — `comparison_dimensions`:
  - `slug` text PK — ej. `ecto.pulgas.ctenocephalides_felis`, `safety.gestation`, `efficacy.fleas.8h_percent`
  - `label` text NOT NULL
  - `category` text NOT NULL — `spectrum`, `efficacy`, `safety`, `formulation`, `duration`, `dosing_presentations`
  - `value_type` text NOT NULL CHECK IN (`boolean`, `text`, `percent`, `enum`)
  - `sort_order` int
- **RF-4** — `comparison_facts` (hechos publicados):
  - `id` uuid PK
  - `subject_product_id` uuid FK → `products` NOT NULL
  - `competitor_id` uuid FK → `competitors` NOT NULL
  - `dimension_slug` text FK → `comparison_dimensions`
  - `value_bool` boolean NULL
  - `value_text` text NULL
  - `value_numeric` numeric NULL — porcentajes 0–100
  - `notes` text NULL — ej. "estudios recientes"
  - `published_version` int NOT NULL
  - `source_document_id` uuid NULL FK → `documents`
  - `source_row` jsonb NULL — trazabilidad import (hoja, fila)
  - UNIQUE (`subject_product_id`, `competitor_id`, `dimension_slug`, `published_version`)
- **RF-5** — `product_comparison_sets` (metadatos del par producto–competidor):
  - `id` uuid PK
  - `subject_product_id` uuid FK
  - `competitor_id` uuid FK
  - `completeness_status` text CHECK IN (`complete`, `incomplete`, `not_applicable`) DEFAULT `incomplete`
  - `published_version` int DEFAULT 0
  - UNIQUE (`subject_product_id`, `competitor_id`)
- **RF-6** — `comparison_gaps` — análogo a `product_dosing_gaps`:
  - `comparison_set_id` FK, `gap_type`, `severity`, `details` jsonb, `resolved_at`
- **RF-7** — `comparison_versions` — snapshot jsonb al publicar un set.
- **RF-8** — `competitive_claims` (opcional v1 si se prefiere solo RAG): si se implementa tabla, campos `subject_product_id`, `claim_text`, `claim_type`, `published_version`. **Alternativa v1 (recomendada):** solo documentos `comparativo` vectorizados para claims; la tabla queda fuera de alcance hasta v1.1.

### Corpus RAG (narrativa)

- **RF-9** — Upload de documentos `kind=comparativo` vía `POST /documents` existente; ETL igual que bitácora pero chunker con secciones tipo bullet/claim (`StructuredMarkdownChunker` — patrón `^[-•]` o párrafos cortos).
- **RF-10** — Metadata de chunk: `topic`, `comparison_target` (nombre competidor si se detecta en título), `claim_type` en `metadata` jsonb.
- **RF-11** — `agent_intent_config` para `comparison_with_competitor`: `document_kinds` = `{bitacora, comparativo}` (migración seed + editable en BO).

### Importación Excel → hechos estructurados

- **RF-12** — `POST /comparison/import` (multipart xlsx):
  - Parsea hojas configurables; v1 mínimo: `ESPECTRO`, `EFECTIVIDAD`.
  - Mapeo columnas → `competitors` (crear si no existe por header).
  - Celdas `SI`/`NO`/texto → `value_bool` / `value_text`.
  - Genera `comparison_gaps` para celdas ambiguas o columnas sin mapear a producto Biomont.
- **RF-13** — Import **no publica**; requiere revisión BO y acción **Publicar set**.

### Backoffice API

- **RF-14** — `GET /competitors`, `POST/PATCH/DELETE` (admin para delete).
- **RF-15** — `GET /products/{id}/comparison-sets` — lista pares con completitud y conteo de facts.
- **RF-16** — `GET /comparison-sets/{id}` — facts borrador + publicados + gaps.
- **RF-17** — `PUT /comparison-sets/{id}/facts` — upsert batch (scientist/admin).
- **RF-18** — `POST /comparison-sets/{id}/publish` — validación completitud mínima (ver RF-19).
- **RF-19** — Set **`complete`** si tiene ≥1 fact en categorías obligatorias configurables (v1 mínimo: `spectrum` con ≥5 dimensiones o flag `force_complete` admin):
  - dimensiones obligatorias default: pulgas (`ecto.pulgas`), garrapatas (`ecto.garrapatas`), gestación (`safety.gestation`) cuando el par es antiparasitario oral.
- **RF-20** — `GET /comparison-dimensions` — catálogo para formularios.
- **RF-21** — `bo_audit_log` en mutaciones.

### Backoffice Web

- **RF-22** — Ruta `/competitors` — CRUD competidores.
- **RF-23** — En `/products/[id]`, pestaña **"Comparativa"**:
  - Selector de competidor (o producto interno vinculado).
  - Matriz editable de hechos por dimensión (según `value_type`).
  - Panel completitud + gaps + **Importar Excel** + **Publicar**.
  - Enlace a documentos `comparativo` vinculados al producto (`document_products`).
- **RF-24** — Badge en listado productos: **"Comparativa incompleta"** si algún set activo del producto está incomplete (config: solo sets marcados `is_priority` en v1.1; v1: cualquier set publicado incompleto).
- **RF-25** — En `/documents`, filtro por kind `comparativo`; upload con kind preseleccionado desde pestaña comparativa del producto.

### Agente — grafo y comportamiento

- **RF-26** — `CompetitorResolver` (determinista):
  - Match nombre competidor en query contra `competitors.normalized_name` (trigram o exacto).
  - Producto subject vía `ProductResolver` previo.
  - Si falta competidor → repregunta: *"¿Con qué producto querés comparar: Bravecto, NexGard, …?"*
  - Comparación **interna** 3M vs M: competidor con `linked_product_id` o alias "proteggo m" cuando subject es 3M.
- **RF-27** — `CompetitorLookup`:
  - Carga facts publicados para `(subject_product_id, competitor_id)`.
  - Clasifica subtipo de pregunta por léxico (barato):
    - `spectrum` → devuelve tabla SI/NO relevante
    - `safety` → gestación/lactancia
    - `efficacy` → porcentajes tiempo
    - `general` → mezcla top-N facts + delega narrativa a RAG
- **RF-28** — Enrutamiento post-`ProductResolver`:

  ```
  comparison_with_competitor
    → CompetitorResolver
    → (needs_competitor?) END repregunta
    → (set incomplete?) END mensaje BO incompleto (análogo 011)
    → route_comparison_mode
         factual_only → CompetitorLookup → TemplateResponse → StateUpdater
         narrative → MetaFilter → HybridRetriever → Answerer (inyecta facts como contexto estructurado en prompt, no como cálculo)
         mixed → Lookup + Answerer con facts en system context
  ```

- **RF-29** — `Answerer` en modo comparación recibe bloque **"Hechos validados"** (JSON compacto) además de chunks RAG; debe citar:
  - facts → `"Fuente: comparativa validada (versión X)"` + opcional documento
  - chunks → citación documental habitual
- **RF-30** — Abstención si no hay facts ni chunks por encima del gate → `no_match` + ticket.
- **RF-31** — No inventar SI/NO ni porcentajes: si el fact no existe, decir que no está cargado y sugerir revisión interna (no alucinar dato de competidor).

### Priorización de datos (híbrido)

| Tipo de afirmación | Fuente primaria |
| ----------------- | --------------- |
| Cobertura parásito X | `comparison_facts` |
| % eficacia a 8 h | `comparison_facts` |
| Seguridad en gestación | `comparison_facts` |
| Claim "9 de 10 perros aceptaron" | RAG `comparativo` |
| Argumento comercial prose | RAG `comparativo` / `bitacora` |

## Requisitos no funcionales

- **RNF-1** — CompetitorLookup < 80 ms p95 (SQL indexado por subject+competitor+version).
- **RNF-2** — Trazabilidad: cada fact lleva `source_row` o `source_document_id`.
- **RNF-3** — Versionado: publicar no muta facts históricos; agente usa última versión publicada.
- **RNF-4** — Separación legal: disclaimer en respuestas comparativas — *"Datos según documentación validada Biomont; verificar regulación local"* (una línea, configurable en system prompt comparativo).

## Criterios de aceptación (Given/When/Then)

- **CA-1 (espectro pulgas)**
  - **Given** facts publicados Proteggo 3M vs Bravecto dimensión pulgas = SI ambos,
  - **When** "¿Proteggo 3M cubre pulgas igual que Bravecto?",
  - **Then** respuesta afirma cobertura con datos estructurados; no inventa %.

- **CA-2 (gestación 3M vs M)**
  - **Given** facts gestación: 3M seguro, M sin estudios mensuales,
  - **When** pregunta comercial #62,
  - **Then** respuesta alineada a facts + cita; sin mezclar productos.

- **CA-3 (claim narrativo)**
  - **Given** documento `comparativo` con claim palatabilidad vectorizado,
  - **When** "¿por qué elegir Proteggo 3M?",
  - **Then** RAG recupera chunk + cita documento; Lookup no contradice.

- **CA-4 (competidor faltante)**
  - **Given** mensaje "comparalo con el otro" sin marca,
  - **When** CompetitorResolver,
  - **Then** repregunta competidor.

- **CA-5 (set incompleto)**
  - **Given** set 3M vs Atrevia incomplete con gaps blocking,
  - **When** comparación factual,
  - **Then** mensaje catálogo incompleto (no datos inventados).

- **CA-6 (import ESPECTRO)**
  - **Given** Excel ESPECTRO con fila Tunga penetrans,
  - **When** import + publicar tras completar gaps,
  - **Then** fact consultable vía API y agente.

- **CA-7 (BO auditoría)**
  - **Given** scientist edita fact,
  - **When** guarda,
  - **Then** `bo_audit_log` registra cambio.

- **CA-8 (MetaFilter)**
  - **Given** config activa,
  - **When** intent comparison,
  - **Then** retrieval incluye `comparativo` y `bitacora`.

## Diseño técnico

### Archivos impactados (previstos)

| Área | Archivos |
| ---- | -------- |
| Migración | `migrations/012_competitor_comparison.sql` |
| Common | `schemas/knowledge.py` (DocumentKind), `db/comparison_repository.py` |
| Agent | `nodes/competitor_resolver.py`, `nodes/competitor_lookup.py`, `graph/graph.py`, `meta_filter` defaults |
| BO API | `comparison_router.py`, `services/comparison_import.py`, ETL chunker patrón comparativo |
| BO Web | `/competitors`, pestaña producto comparativa |
| Eval | golden_set casos comparison |

### Chunking `comparativo`

Extender `StructuredMarkdownChunker` con patrones para hoja Claims convertida a markdown (lista de bullets). Si el upload es Excel, pipeline opcional: exportar hoja a markdown en ingest (sin nueva dependencia si se usa parsing openpyxl en backoffice-api — justificar en PR si se agrega).

### Respuesta factual (plantilla)

> Comparando **{subject}** con **{competitor}** (datos validados v{version}):  
> - {dimensión 1}: {valor}  
> - {dimensión 2}: {valor}  
> Fuentes: comparativa Biomont.

El **Answerer** solo para preguntas `mixed`/`narrative`; modo `factual_only` puede evitar LLM (como Calculator) si el producto quiere máxima fidelidad — **decisión v1:** factual_only sin LLM; mixed con LLM y temperature 0.

## Plan de pruebas

- Unitarios: import ESPECTRO (fixture), resolver competidor, template factual.
- HTTP: CRUD competitors, publish set, 422 incompleto.
- Grafo: rutas comparison factual vs narrative.
- Golden set: ≥15 casos (3M vs M gestación, vs Bravecto pulgas, claim RAG).

## Observabilidad

- `comparison_lookup` log: `subject_product_id`, `competitor_id`, `mode`, `facts_count`.
- `comparison_blocked` log: `incomplete_set`, `missing_competitor`.
- `graph_trace` payloads en `CompetitorResolver` / `CompetitorLookup`.

## Riesgos y rollback

| Riesgo | Mitigación |
| ------ | ---------- |
| Matriz mal importada | gaps + revisión BO antes de publicar; `source_row` |
| Datos competencia desactualizados | `published_at`, versión, proceso de revisión científica |
| LLM mezcla facts y alucina | factual_only sin LLM; Answerer con facts en bloque fijo "no modificar cifras" |
| Enum document_kind migration | ALTER TYPE en transacción; down script documentado |
| Solapamiento con RAG bitácora | facts primero; RAG complementa |

### Rollback

1. Deshabilitar rutas comparison en grafo (feature flag `AGENT_COMPARISON_STRUCTURED=false`).
2. Revertir deploy.
3. Migration 012 down (elimina tablas; enum value `comparativo` puede quedar huérfano — down debe documentar).
4. Intent vuelve a solo `bitacora` en config.

## Coordinación con 011

| Capa | 011 Dosis | 012 Comparativa |
| ---- | --------- | --------------- |
| Hub `/products/[id]` | Pestaña Dosis | Pestaña Comparativa |
| Gaps + publish | `product_dosing_gaps` | `comparison_gaps` |
| Import Excel | Hoja presentaciones | Hojas ESPECTRO/EFECTIVIDAD |
| Agente | Calculator | CompetitorLookup |

Implementación sugerida: **011 primero** (criterio 0% error más estricto), **012 en paralelo** tras migración 011 en BO UI patterns.

## Preguntas abiertas (resolver con laboratorio antes de implementar)

1. ¿Listado cerrado de competidores v1 (solo los del Excel) o alta libre en BO?
2. ¿Precios del Excel entran alguna vez al agente?
3. ¿Dimensiones obligatorias para declarar un set `complete`?
4. ¿Comparativas de líneas no antiparasitarias (tramadol, hepatin) entran en v1 o solo RAG?
