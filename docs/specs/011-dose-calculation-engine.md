# 011 - Motor de cálculo de dosis (datos estructurados + backoffice)

## Contexto y objetivo

Hoy el agente responde preguntas de dosis vía RAG (`dosage_question` → `HybridRetriever` → `Answerer`). Eso es adecuado para **información narrativa** (indicaciones, contraindicaciones en prosa), pero **no cumple** el criterio de negocio del sprint: **0% de error** en la selección de presentación / tableta según peso del animal.

El nodo `Calculator` existe como placeholder y no está enrutado (`services/agent/src/app/agent/graph/nodes/calculator.py`). La spec [003](./003-langgraph-hybrid-rag-and-knowledge-restructure.md) previó tablas clínicas en ADR fase 2 (`product_presentations`, `dosing_ranges`).

**Fuentes de verdad del laboratorio (evidencia externa al repo):**

- Hoja `Presentaciónes y dosis` del Excel *COMPARATIVO COMERCIAL PROTEGGO 3M y M* — bandas de peso → mg por presentación (Proteggo 3M / M y competencia).
- Balotario: pocas preguntas explícitas de cálculo; el uso real será del tipo *"perro de 25 kg, ¿qué Proteggo le doy?"*.

**Objetivo:** implementar un motor **determinista** (sin LLM en el cálculo) alimentado por tablas en Postgres, editable y auditable desde el backoffice, con señalización de productos **incompletos** cuando el ETL no alcanza, y ruteo dedicado en el grafo LangGraph.

**Alcance sprint 2 (decisión producto):** multi-especie desde v1 (perfil por `product_id` + `species`); modos **`formula`** (ej. 1 ml/kg, 1 comp/10 kg) y **`weight_band`** (0–15 kg → X ml/mg); unidades **`ml`** (inyectables) y **`mg`/`tablets`** (sólidos). La respuesta debe citar fórmula/regla, valores de entrada, resultado y versión publicada.

**Relación con otras specs:** extiende [003](./003-langgraph-hybrid-rag-and-knowledge-restructure.md) (grafo + Calculator), [004](./004-backoffice-products-documents-and-agent-decisions.md) (hub productos), [008](./008-agent-config-from-backoffice-db.md) (intents). El comparador híbrido va en [012](./012-competitor-comparison-hybrid.md).

## Alcance / fuera de alcance

### En alcance

- Nuevo intent `dose_calculation` (enum + `agent_intent_config` + clasificador).
- Tablas estructuradas de presentaciones y reglas de uso (sin embeddings).
- Nodos `WeightExtractor` (parser determinista) y `Calculator` (lookup + plantilla de respuesta).
- Ruteo condicional en el grafo tras `ProductResolver`.
- APIs REST backoffice: CRUD presentaciones, reglas, importación asistida, estado de completitud por producto.
- UI backoffice: pestaña **"Dosis / presentaciones"** en `/products/[id]` + listado de productos con badge de completitud.
- Importador desde Excel (hoja de presentaciones) → staging → revisión manual → publicación.
- Persistencia en `agent_decisions.graph_trace` de inputs/outputs del cálculo (auditoría reproducible).
- Golden set y tests unitarios exhaustivos de bordes de bandas.

### Fuera de alcance (v1)

- Cálculo de **mg totales por mg/kg** cuando la etiqueta solo define presentación por banda de peso (v1 = recomendar **presentación comercial**, no recalcular principio activo).
- Conversión lb → kg automática en v1 (repreguntar unidad no reconocida).
- Dosis en especies distintas a perro si no hay filas cargadas (abstención).
- Editar valores desde la UI de **chunks** RAG (sigue siendo solo lectura en documentos).
- Motor de dosis para productos sin flag `supports_dose_calculation` (quedan en flujo RAG `dosage_question`).

## Estado actual (evidencia de esquema)

`DATABASE_URL` no disponible en el entorno de redacción; evidencia tomada de migraciones y código.

### Tablas existentes relevantes

| Tabla | Columnas / uso |
| ----- | -------------- |
| `products` | `id`, `name`, `brand`, `duration_type`, `description`, `country_iso` — migración `004_knowledge_restructure.sql` |
| `product_aliases` | resolución determinista en `ProductResolver` |
| `documents` + `document_products` | corpus RAG; `kind` ∈ `ficha_tecnica`, `bitacora`, `balotario` |
| `knowledge_chunks` | `contains_dose`, `species[]` — útil para detectar candidatos ETL, **no** para cálculo |
| `agent_intent_config` | intents configurables; hoy `dosage_question` filtra kinds RAG |
| `agent_decisions` | `graph_trace` jsonb, `retrieved`, `decision` |
| `bo_audit_log` | auditoría mutaciones backoffice |

### Grafo actual (`services/agent/src/app/agent/graph/graph.py`)

```
IntentClassifier → ProductResolver → MetaFilter → HybridRetriever → Answerer → StateUpdater
```

`Calculator` no está en el grafo compilado.

### Enum `Intent` actual

`dosage_question`, `clinical_protocol`, `comparison_with_competitor`, `safety_question`, `chitchat`, `out_of_scope` — sin `dose_calculation`.

## Requisitos funcionales

### Modelo de datos

`Migraciones necesarias: sí` — script `migrations/011_dose_calculation.sql` (+ `.down.sql`).

- **RF-1** — `product_dosing_profiles` (1:N con `products`, una fila por especie):
  - `id` uuid PK
  - `product_id` uuid FK → `products` ON DELETE CASCADE
  - `species` text NOT NULL — ej. `canine`, `feline`, `bovine`, `calf`
  - UNIQUE (`product_id`, `species`)
  - `supports_dose_calculation` boolean NOT NULL DEFAULT false
  - `min_age_weeks` int NOT NULL DEFAULT 8
  - `min_weight_kg` numeric(6,2) NOT NULL DEFAULT 2.0
  - `max_weight_kg` numeric(6,2) NULL — NULL = sin tope documentado
  - `completeness_status` text NOT NULL DEFAULT 'incomplete'
    CHECK IN (`complete`, `incomplete`, `not_applicable`)
  - `completeness_notes` text NULL — resumen legible para BO
  - `published_version` int NOT NULL DEFAULT 0 — 0 = nunca publicado
  - `source_document_id` uuid NULL FK → `documents`
  - `updated_at`, `updated_by` uuid FK → `bo_users`
- **RF-2** — `product_dosing_rules` (reglas por perfil; reemplaza `product_presentations`):
  - `id` uuid PK
  - `profile_id` uuid FK → `product_dosing_profiles` ON DELETE CASCADE
  - `rule_type` text NOT NULL CHECK IN (`formula`, `weight_band`)
  - `label` text NULL — ej. `PROTEGGO 3M 250 mg`, `1 comp/10 kg`
  - **Fórmula:** `formula_numerator`, `formula_denominator`, `formula_per_kg` (default true), `output_unit` ∈ `ml`|`mg`|`tablets`|`doses`
  - **Rango:** `weight_min_kg`, `weight_max_kg`, `output_value`, `output_unit`, `weight_min_inclusive`, `weight_max_inclusive`
  - `min_output`, `max_output` numeric NULL — topes post-cálculo
  - `sort_order` int NOT NULL DEFAULT 0
  - `is_active` boolean NOT NULL DEFAULT true
  - `published_version` int NOT NULL DEFAULT 0 — 0 = borrador
- **RF-3** — `product_dosing_gaps` (ítems que el BO debe completar a mano):
  - `id` uuid PK
  - `product_id` uuid FK
  - `gap_type` text NOT NULL — ej. `missing_presentation_band`, `missing_strength_mg`, `missing_profile`, `import_unparsed_row`
  - `severity` text NOT NULL DEFAULT 'blocking' CHECK IN (`blocking`, `warning`)
  - `details` jsonb NOT NULL — payload estructurado (fila Excel, rango, etc.)
  - `resolved_at` timestamptz NULL
  - `created_at` timestamptz NOT NULL DEFAULT now()
- **RF-4** — `product_dosing_versions` (historial publicado, auditoría):
  - `id` uuid PK
  - `product_id` uuid FK
  - `version` int NOT NULL
  - `snapshot` jsonb NOT NULL — presentaciones + profile al publicar
  - `published_by` uuid FK → `bo_users`
  - `published_at` timestamptz NOT NULL DEFAULT now()
  - UNIQUE (`product_id`, `version`)
- **RF-5** — Semántica de **publicación**:
  - Borrador: filas en `product_presentations` con `published_version = 0` (o tabla staging separada `product_presentations_draft` si simplifica queries — elegir una estrategia en implementación y documentarla).
  - **Publicar** copia borrador → `published_version = MAX+1`, actualiza `product_dosing_profiles.completeness_status` y limpia `product_dosing_gaps` resueltos.
  - El agente **solo lee** la versión publicada activa (última `product_dosing_versions` o `published_version` máximo).

### Reglas de completitud (backoffice)

- **RF-6** — Un producto con `supports_dose_calculation = true` está **`complete`** solo si:
  - existe perfil con `min_age_weeks` / `min_weight_kg` definidos;
  - hay al menos una presentación activa;
  - las bandas `[weight_min_kg, weight_max_kg]` **cubren sin huecos** el intervalo `[min_weight_kg, max_weight_kg]` del perfil (misma semántica de inclusión documentada en UI);
  - no hay gaps `blocking` abiertos.
- **RF-7** — Tras import ETL / reingesta asistida, si faltan datos (ej. celda vacía de mg en banda 10–20 kg de Proteggo M en el Excel de referencia), el sistema:
  - crea `product_dosing_gaps` con `gap_type = missing_strength_mg`;
  - deja `completeness_status = incomplete`;
  - muestra en `/products` badge **"Dosis incompleta"** y en detalle lista de gaps con CTA **"Completar manualmente"**.
- **RF-8** — El listado `/products` incluye columnas: `dosing_completeness_status`, `open_gaps_count`, `supports_dose_calculation`.

### Importación asistida (ETL → estructurado)

- **RF-9** — `POST /products/{id}/dosing/import` (multipart: xlsx/csv o referencia a documento comparativo ya subido):
  - Rol: `admin`, `scientist`.
  - Parsea hoja tipo *Presentaciónes y dosis* (columnas Proteggo 3M / M u homólogas configurables).
  - **No publica** automáticamente: llena borrador + gaps.
  - Respuesta: `{ imported_rows, gaps_created[], preview_presentations[] }`.
- **RF-10** — Heurística post-import: si el mismo producto tiene documento `ficha_tecnica` validado con chunks `contains_dose = true`, marcar gap `warning` sugiriendo revisión cruzada (no bloquea publicación).

### Backoffice API

- **RF-11** — `GET /products/{id}/dosing` — perfil + presentaciones borrador + publicadas + gaps abiertos.
- **RF-12** — `PUT /products/{id}/dosing/profile` — actualizar perfil y `supports_dose_calculation`.
- **RF-13** — `POST /products/{id}/dosing/presentations` — crear; `PATCH/DELETE` por id.
- **RF-14** — `POST /products/{id}/dosing/publish` — valida completitud; `422` con lista de gaps si no pasa.
- **RF-15** — `GET /products/{id}/dosing/versions` — historial para auditoría.
- **RF-16** — `bo_audit_log` en create/update/delete/publish/import (`entity` ∈ `product_dosing_profiles`, `product_presentations`, `product_dosing_gaps`).

### Backoffice Web

- **RF-17** — En `/products/[id]`, pestaña **"Dosis / presentaciones"**:
  - Tabla editable de bandas (peso min/max, mg, label, activo).
  - Panel **Completitud** (semáforo + lista de gaps).
  - Botones: **Importar Excel**, **Guardar borrador**, **Publicar**.
  - Historial de versiones (solo lectura para `viewer`).
- **RF-18** — En `/products`, columna/badge de completitud; filtro rápido "Dosis incompleta".
- **RF-19** — Roles: ver todos; mutar `admin`/`scientist`; publicar solo `admin` (alineado a activar config agente).

### Agente — intent y grafo

- **RF-20** — Nuevo `Intent.dose_calculation` en `agent_graph.py` + fila en seed/migración `agent_intent_config` con hint del clasificador del tipo: *calcular presentación, cuántas tabletas, perro de X kg, qué tableta*.
- **RF-21** — Mantener `dosage_question` para preguntas **informativas** sin cálculo (posología en texto, ranurado, administración con/sin alimento).
- **RF-22** — `WeightExtractor` (determinista, sin LLM):
  - Extrae peso en kg con regex (`25 kg`, `25kg`, `25 kilos`, `25,5`).
  - Extrae especie si menciona gato → v1 repregunta o abstención si el producto es solo canine.
  - Si no hay peso parseable → estado `needs_weight` (no Calculator).
- **RF-23** — `Calculator`:
  - Entrada: `product_id`, `weight_kg`, `published_version`.
  - Lookup SQL: una fila en `product_presentations` activa que contenga el peso según flags inclusive.
  - Salida estructurada: `{ presentation_label, strength_mg, weight_band, profile_version, source_document_id }`.
  - **Cero llamadas LLM** en este nodo.
- **RF-24** — `ResponseFormatter` (puede ser función dentro de Calculator o nodo ligero): arma texto fijo:

  > Para un perro de **{weight} kg** y el producto **{product}**, la presentación indicada es **{label}** ({strength} mg), rango **{min}–{max} kg**.  
  > Fuente: datos validados del backoffice (versión {version}).

- **RF-25** — Ruteo en `build_graph`:

  ```
  ProductResolver ─(ambiguous)→ END
        │ (ok)
        ▼
  route_by_intent
    dose_calculation + needs_weight → END (repregunta peso)
    dose_calculation + weight_ok → Calculator → StateUpdater → END
    dose_calculation + product_incomplete → END (mensaje + ticket opcional)
    otro → MetaFilter → … (flujo actual)
  ```

- **RF-26** — Si `completeness_status != complete` para el producto resuelto → **no calcular**; respuesta:

  > "No puedo calcular la dosis de *{producto}* porque faltan datos en el catálogo. El equipo técnico debe completarlos en el backoffice."

  Opcional: ticket `no_info` con metadata `dosing_incomplete`.

- **RF-27** — Repregunta peso (plantilla):

  > "Para indicarte la presentación correcta de *{producto}*, necesito el **peso del perro en kg** (ej. 25 kg)."

- **RF-28** — `graph_trace` incluye payload Calculator: `{ weight_kg, presentation_id, band, published_version, outcome }`.

### Orquestador

- **RF-29** — Respuestas Calculator con `decision = answered` sin exigir citaciones RAG de chunks; citación = referencia a versión de datos estructurados + documento fuente si existe.
- **RF-30** — Confirmación de producto (`maybe_product_confirmation_reply`) se mantiene antes del texto de dosis.

## Requisitos no funcionales

- **RNF-1** — Latencia Calculator + WeightExtractor < 50 ms p95 (solo SQL local).
- **RNF-2** — Idempotencia: misma entrada (producto, peso, versión) → misma salida (tests obligatorios).
- **RNF-3** — Trazabilidad: toda publicación en BO deja `product_dosing_versions.snapshot`.
- **RNF-4** — Seguridad: endpoints mutables con JWT + RBAC; sin exponer borradores incompletos al agente.

## Criterios de aceptación (Given/When/Then)

- **CA-1 (cálculo feliz Proteggo 3M)**
  - **Given** producto Proteggo 3M publicado con banda 20–40 kg → 1000 mg y peso 25 kg,
  - **When** el RTC pregunta "perro de 25 kg qué proteggo 3m le doy",
  - **Then** intent `dose_calculation`, respuesta incluye `1000 mg` y rango 20–40 kg, sin llamada a HybridRetriever.

- **CA-2 (borde inclusivo)**
  - **Given** banda >4.5–10 kg con `weight_min_inclusive=false` según ficha importada,
  - **When** peso = 4.5 kg,
  - **Then** no coincide esa banda; cae en la banda correcta o abstención documentada (test con valor esperado fijado en golden set).

- **CA-3 (sin peso → repregunta)**
  - **Given** producto completo,
  - **When** "qué tableta de proteggo m" sin kg,
  - **Then** repregunta peso; `decision` ≠ `answered` con cálculo; no se invoca Calculator.

- **CA-4 (producto incompleto)**
  - **Given** Proteggo M con gap blocking en banda 10–20 kg,
  - **When** pregunta de cálculo con peso 15 kg,
  - **Then** mensaje de catálogo incompleto; no devuelve mg inventado.

- **CA-5 (ambigüedad producto primero)**
  - **Given** mensaje "proteggo" sin M/3M,
  - **When** llega al resolver,
  - **Then** repregunta producto **antes** de pedir peso.

- **CA-6 (0% error regresión)**
  - **Given** golden set con ≥30 casos (cada banda × peso centro y bordes),
  - **When** se ejecuta eval,
  - **Then** 100% coincidencia exacta en `strength_mg` y `label`.

- **CA-7 (BO publicar)**
  - **Given** scientist completa gaps manualmente,
  - **When** admin publica,
  - **Then** `completeness_status=complete`, agente calcula en CA-1.

- **CA-8 (import genera gaps)**
  - **Given** Excel con celda mg vacía en una banda,
  - **When** import,
  - **Then** `product_dosing_gaps` blocking y badge incompleto en listado.

- **CA-9 (dosage_question sigue en RAG)**
  - **Given** "¿las tabletas son ranuradas para dosificar?",
  - **When** clasifica,
  - **Then** intent `dosage_question` (no `dose_calculation`) y flujo RAG habitual.

- **CA-10 (auditoría BO)**
  - **Given** admin edita una presentación,
  - **When** guarda,
  - **Then** fila en `bo_audit_log` con before/after.

## Diseño técnico

### Archivos impactados (previstos)

| Área | Archivos |
| ---- | -------- |
| Migración | `migrations/011_dose_calculation.sql`, `.down.sql` |
| Common | `schemas/agent_graph.py`, `db/dosing_repository.py`, schemas Pydantic dosing |
| Agent | `graph/graph.py`, `nodes/calculator.py`, `nodes/weight_extractor.py`, `orchestrator.py` |
| BO API | `api/dosing_router.py` o rutas bajo `products_router.py`, `services/dosing_import.py` |
| BO Web | `products/[id]/` pestaña dosing, listado productos |
| Eval | `evaluation/golden_set.yaml`, tests agent |

### Parser de peso (determinista)

Orden de intento:

1. `(?:perro|can|paciente)?\s*(?:de\s+)?(\d+(?:[.,]\d+)?)\s*(?:kg|kilos?|kilo)\b`
2. Si múltiples números, preferir el más cercano a token `kg`.
3. Rechazar si unidad `lb` sin conversión en v1 → repregunta pidiendo kg.

### Separación `dosage_question` vs `dose_calculation`

| Intent | Ejemplo | Pipeline |
| ------ | ------- | -------- |
| `dose_calculation` | "perro 25 kg qué proteggo" | WeightExtractor → Calculator |
| `dosage_question` | "¿puedo partir la tableta?", "dosis en gestación" | RAG |

Calibración léxica en `intent_classifier.py`: si hay peso parseable (kg) y frase de cálculo (`que dosis le doy`, `que tableta`, `calcular`, etc.) → `dose_calculation`; excluye indicación/gestación/administración informativa (`dosage_question` → RAG). Migración `013_*` actualiza `classifier_hint` en config activa.

## Plan de pruebas

- **Unitarios:** parser peso, lookup bandas (inclusivos/exclusivos), validador completitud, importador Excel (fixture del comparativo Proteggo).
- **Integración SQL:** `DosingRepository` con asyncpg mock o DB test.
- **HTTP:** endpoints dosing (happy path, 422 publish incompleto, 403 viewer).
- **Grafo:** `test_graph_pipeline.py` — rama Calculator, repregunta peso, producto incompleto.
- **Eval:** `test_golden_set_eval.py` — casos `@pytest.mark dose_calc` con aserción exacta.

## Observabilidad

- Log `dose_calc_completed` con `product_id`, `weight_kg`, `presentation_id`, `version` (sin teléfono completo).
- Log `dose_calc_blocked` con `reason` ∈ `incomplete_catalog`, `missing_weight`, `out_of_range`.
- Métrica derivable: ratio `dose_calc_blocked / dose_calc_requests` en dashboard futuro.

## Riesgos y rollback

| Riesgo | Mitigación |
| ------ | ---------- |
| Extracción de peso poco confiable | Parser determinista + repregunta; nunca asumir peso por defecto |
| ETL deja bandas incompletas | `product_dosing_gaps` + badge BO + bloqueo de publicación |
| Confusión Proteggo M / 3M | ProductResolver antes de Calculator; tablas separadas por `product_id` |
| RTC pregunta cálculo para producto sin perfil | `supports_dose_calculation=false` → abstención o deriva a RAG con mensaje claro |
| Regresión en preguntas informativas de dosis | Mantener `dosage_question`; tests CA-9 |

### Rollback

1. Desactivar intent `dose_calculation` en `agent_intent_config` (`is_enabled=false`).
2. Revertir deploy agent + backoffice-api + web.
3. `apply_migration.sh 011 --down` (elimina tablas dosing; no toca RAG).
4. El grafo vuelve al flujo lineal actual.

## Coordinación

- Implementar **antes o en paralelo** con [012](./012-competitor-comparison-hybrid.md) solo en capas compartidas (navegación productos); sin dependencia funcional.
- Tras merge: seed inicial Proteggo 3M y Proteggo M desde Excel de referencia; validar con laboratorio la banda 10–20 kg de Proteggo M (dato faltante en fuente).
