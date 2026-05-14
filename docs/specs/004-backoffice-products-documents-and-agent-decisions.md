# 004 - Backoffice: productos, enriquecimiento de documentos y auditoria de decisiones del agente

## Contexto y objetivo

Tras la spec [003](./003-langgraph-hybrid-rag-and-knowledge-restructure.md), el conocimiento queda distribuido en varias tablas (`products`, `product_aliases`, `document_sections`, `knowledge_chunks`, `faq_entries`) y cada turno del agente deja trazas en `agent_decisions` (incl. `graph_trace` tras el grafo LangGraph). El backoffice web hoy ofrece CRUD basico de **documentos** con vista de **markdown** plano, pero **no** permite:

1. Gestionar **productos y aliases** desde la UI (hoy depende de `scripts/bootstrap_products.sql` / seed YAML y SQL manual).
2. Inspeccionar **que fragmentos** usa realmente el retrieval (`document_sections`, `knowledge_chunks`, y — para compatibilidad — `document_chunks` legacy).
3. **Auditar** las **decisiones del agente** junto con el contexto de conversacion: por que respondio `no_match`, que chunks figuraron en `retrieved`, que nodos ejecuto el grafo, etc.

**Objetivo**: dotar al backoffice de tres capacidades coherentes entre si — **catalogo de productos**, **visibilidad del corpus por documento**, **panel de auditoria de decisiones** — para operacion interna, soporte y revision cientifica, sin exponer datos sensibles fuera de usuarios autenticados.

## Alcance / fuera de alcance

### En alcance

- **Seccion “Productos”** (nueva ruta en el dashboard): CRUD sobre `public.products` y `public.product_aliases` con formularios validados, listados paginados, y confirmacion en borrados destructivos.
- **Seccion “Decisiones del agente”** (nueva ruta): listado paginado y filtrable de `public.agent_decisions` con union/joins a `messages`, `conversations`, `rtc_users` (telefono, nombre) para contexto humano; detalle de una decision mostrando `decision`, `reasoning`, `retrieved`, `top_similarity`, `system_prompt_version`, `graph_trace` (JSON pretty-print / tabla de nodos), y enlace al mensaje asistente asociado.
- **Mejora de la vista “Documento”** (`/documents/[id]`): mas alla del markdown, pestañas o acordeon con:
  - **Secciones**: arbol o lista ordenada por `section_index` de `document_sections` (titulo, `section_kind`, preview de `raw_text` truncado, navegacion al chunk).
  - **Chunks de conocimiento**: tabla de `knowledge_chunks` del documento (indice, `kind`, `section_type`, `contains_dose` / `contains_table`, fragmento de `content`, `token_count`, `metadata`); paginacion server-side (p. ej. 50 filas).
  - **Chunks legacy** (opcional pero recomendado para auditoria): tabla de `document_chunks` si existen filas, para comparar ingest antiguo vs nuevo.
  - **FAQ** (si `kind = balotario` o hay filas en `faq_entries`): listado de preguntas/respuestas enlazadas al documento.
- **APIs REST** en `backoffice-api` para todo lo anterior, autenticadas con el mismo modelo de sesion/JWT del BO, con **RBAC** explicito (ver tabla roles mas abajo).
- **Tests**: endpoints con `httpx`/pytest; componentes criticos del front con pruebas minimas donde ya exista convencion en el monorepo.

### Fuera de alcance (v1)

- **Re-ejecutar** embedding o regenerar chunks desde el BO (eso sigue siendo ETL / `reingest`). La spec solo permite **leer** y gestionar **catalogo** y **metadatos** de productos/aliases, no reprocesar PDFs.
- **Edicion inline** del texto de `knowledge_chunks` o `document_sections` en base (riesgo de desalinear embeddings). Si en el futuro se requiere, va en spec aparte con invalidacion de vectores.
- **Export masivo** CSV de decisiones (puede anadirse como RF opcional en v1.1).
- **Realtime**: la lista de decisiones puede ser polling o carga manual de “refrescar”; WebSocket queda fuera de v1.
- **Borrado en cascada de productos** con documentos colgando: la UI debe advertir y listar dependencias (`documents.product_id`); el borrado de producto con FK activa puede estar **restringido** hasta desasociar documentos (comportamiento ya definido por `ON DELETE SET NULL` en `documents.product_id`).

## Requisitos funcionales

### Productos y aliases

- **RF-P1**: Listar productos con columnas minimas: nombre, marca, `duration_type`, `country_iso`, cantidad de aliases, cantidad de documentos enlazados (`COUNT` de `documents` por `product_id`).
- **RF-P2**: Crear producto: campos alineados con `products` (`name`, `brand`, `duration_type`, `description`, `country_iso` opcional). Validar unicidad logica acorde a `uq_products_name_country` (mensaje de error claro si conflicto).
- **RF-P3**: Editar producto (mismos campos editables).
- **RF-P4**: Eliminar producto: solo roles `admin` (ver RBAC); confirmacion modal; si existen `documents` con `product_id`, mostrar aviso y opcion de **desasociar** (set NULL) antes de borrar, o impedir borrado hasta desasociar (definir una politica unica en implementacion y documentarla en el modal).
- **RF-P5**: Gestion de **aliases** por producto: listar, agregar, editar texto de alias, eliminar alias. Respetar unicidad `(product_id, normalized_alias)`; no permitir duplicar el mismo alias normalizado para el mismo producto.

### Decisiones del agente

- **RF-D1**: Listado con filtros minimos: `decision` (enum), rango de fechas (`created_at`), busqueda por telefono (`rtc_users.phone_e164` normalizado) o por `conversation_id` UUID.
- **RF-D2**: Vista detalle con todos los campos persistidos en `agent_decisions` y contexto: snippet del mensaje usuario previo si aplica (via `messages` encadenados por conversacion), cuerpo del mensaje del asistente vinculado a `message_id` cuando exista.
- **RF-D3**: Visualizar `retrieved` como lista legible (document_id, chunk_id, similarity), no solo JSON crudo.
- **RF-D4**: Visualizar `graph_trace` como lista de pasos (nodo, latency_ms, outcome, payload colapsable) cuando el array no este vacio.

### Documentos (mejora)

- **RF-DOC1**: Mantener la vista actual de markdown como primera pestaña **“Texto / Markdown”**.
- **RF-DOC2**: Pestaña **“Secciones”**: cargar `document_sections` ordenadas por `section_index`; mostrar jerarquia (`parent_section_id`); longitud de texto; sin cargar `raw_text` completo en el listado inicial si supera N KB (usar preview + “expandir”).
- **RF-DOC3**: Pestaña **“Chunks (retrieval)”**: filas de `knowledge_chunks` con filtros opcionales por `kind` y `section_type`; busqueda full-text del campo `content` en servidor (LIKE o `tsv` segun performance) opcional para v1.
- **RF-DOC4**: Pestaña **“Chunks legacy”** si hay `document_chunks` para ese `document_id`.
- **RF-DOC5**: Pestaña **“FAQ”** si hay entradas en `faq_entries` para el documento.

## Requisitos no funcionales

- **RNF-1**: Paginacion obligatoria en listados (productos, aliases embebidos con limite, decisiones, chunks). Tamano de pagina por defecto 25-50; maximo hard cap en API (p. ej. 100).
- **RNF-2**: Latencia: detalle de documento con tabs no debe cargar todos los chunks a la vez; usar lazy load por pestaña + paginacion.
- **RNF-3**: Seguridad: todos los endpoints `401` sin sesion; `403` si el rol no alcanza. No exponer `OPENAI` keys ni contenido de `.env`.
- **RNF-4**: Auditoria: registrar en `bo_audit_log` acciones mutantes sobre productos/aliases (create/update/delete) con `before`/`after` similar a `documents` hoy.

## Roles y autorizacion (RBAC)

Alineado a `public.bo_role` (`viewer`, `scientist`, `admin`):

| Accion | viewer | scientist | admin |
| ------ | :----: | :-------: | :---: |
| Ver productos / aliases | si | si | si |
| Crear / editar productos y aliases | no | si | si |
| Eliminar producto | no | no | si |
| Ver decisiones del agente | si | si | si |
| Ver secciones / chunks / FAQ en documento | si | si | si |

Ajuste: si el equipo prefiere **solo admin** para productos mutables, estrechar la columna scientist en una revision rapida antes de implementar.

## Criterios de aceptacion (Given/When/Then)

- **CA-1 (CRUD producto feliz)**
  - **Given** un usuario `scientist` autenticado,
  - **When** crea un producto valido sin colision de unicidad,
  - **Then** aparece en el listado y persiste en `products`.

- **CA-2 (alias duplicado)**
  - **Given** un producto con alias “proteggo 3m”,
  - **When** intenta agregar otro alias que normaliza igual,
  - **Then** la API responde 409/422 con mensaje claro y no inserta duplicado.

- **CA-3 (listado decisiones)**
  - **Given** al menos una fila en `agent_decisions`,
  - **When** un `viewer` abre la seccion Decisiones,
  - **Then** ve la fila con decision, fecha y datos de contexto (RTC/conversacion) segun diseno.

- **CA-4 (detalle decision con grafo)**
  - **Given** una decision con `graph_trace` no vacio,
  - **When** abre el detalle,
  - **Then** ve los nodos en orden con latencias y puede expandir `payload`.

- **CA-5 (documento: pestaña chunks)**
  - **Given** un documento con filas en `knowledge_chunks`,
  - **When** abre la pestaña correspondiente,
  - **Then** ve al menos el primer lote paginado y puede avanzar de pagina.

- **CA-6 (documento sin chunks nuevos)**
  - **Given** un documento solo ingerido con pipeline antiguo (solo `document_chunks`),
  - **When** abre el documento,
  - **Then** la pestaña legacy muestra datos y la pestaña “Chunks (retrieval)” indica vacio o mensaje explicativo invitando a reingestar.

- **CA-7 (audit log)**
  - **Given** un `admin` elimina un alias,
  - **When** la operacion termina,
  - **Then** existe entrada en `bo_audit_log` con accion identificable.

## Diseno tecnico

### Backend (`services/backoffice-api`)

- **Rutas nuevas** (prefijo bajo el router API existente, p. ej. `/api` o el que use el BO hoy):
  - `GET/POST /products`, `GET/PATCH/DELETE /products/{id}`
  - `GET/POST /products/{id}/aliases`, `PATCH/DELETE /products/{id}/aliases/{alias_id}`
  - `GET /agent-decisions` (query params: filtros + `page`, `page_size`)
  - `GET /agent-decisions/{id}`
  - `GET /documents/{id}/sections` (paginado si hiciera falta por tamano)
  - `GET /documents/{id}/knowledge-chunks` (paginado, sort por `chunk_index`)
  - `GET /documents/{id}/document-chunks` (legacy, paginado)
  - `GET /documents/{id}/faq-entries`

Encapsular SQL en repositorios (`ProductRepository` extendido o `ProductAdminRepository`, `AgentDecisionRepository`, extension de `DocumentRepository`) cumpliendo `.cursor/rules/dependency-constraints.mdc` (sin SQL en handlers sueltos).

### Frontend (`services/backoffice-web`)

- Nuevas paginas bajo `(dashboard)`:
  - `/products`, `/products/[id]` o modal de edicion inline — segun patron ya usado en otras entidades.
  - `/agent-decisions`, `/agent-decisions/[id]`
- Ampliar `/documents/[id]` con layout de tabs (shadcn Tabs si ya esta disponible en el stack).

### Modelo de datos (existente; sin cambios obligatorios)

- `products`, `product_aliases` — migracion [004](../../migrations/004_knowledge_restructure.sql).
- `agent_decisions` + columna `graph_trace` jsonb — misma migracion.
- `document_sections`, `knowledge_chunks`, `faq_entries`, `document_chunks`, `documents`.

### Decisiones de diseno

- **IDs**: todas las respuestas API usan UUID en string como en el resto del BO.
- **Orden de tabs documento**: Markdown → Secciones → Chunks retrieval → FAQ (si aplica) → Legacy.
- **Enlace cruzado**: desde una decision, link a `/documents/{document_id}` si `retrieved` contiene document_ids parseables; desde producto, listado de documentos con ese `product_id`.

## Migraciones necesarias

**Migraciones necesarias: no** para la funcionalidad base descrita (todo lee tablas existentes).

**Opcional (si perf de listados lo exige)**:

- Indice compuesto adicional en `agent_decisions(created_at DESC)` ya cubierto parcialmente por `idx_agent_decisions_decision`; evaluar `CREATE INDEX ... ON agent_decisions(created_at DESC)` dedicado si EXPLAIN muestra seq scan en orden cronologico global.

Evidencia de schema: obtener `\d+` de tablas involucradas via skill `manage-biomont-db` antes de cargar datos masivos en prod.

## Plan de pruebas

- **API**: pytest por endpoint — 200 feliz, 401 sin auth, 403 rol incorrecto, 404 id inexistente, 409 conflicto unicidad producto/alias.
- **Integracion**: 1 test que inserta decision fake (fixture) y lista con filtro.
- **Front**: smoke manual o test E2E ligero si el proyecto ya usa Playwright; si no, checklist QA en PR.

## Observabilidad

- Logs estructurados en backoffice-api: `event=products_mutate`, `event=agent_decisions_list`, `latency_ms`, `actor_id`, `request_id`.
- No loguear cuerpos completos de chunks en INFO (truncar o solo en DEBUG).

## Riesgos y rollback

| Riesgo | Mitigacion |
| ------ | ---------- |
| Listados lentos con muchas decisiones/chunks | Paginacion estricta; indices opcionales; no SELECT `content` ilimitado |
| Borrado de producto rompe expectativas de ETL | UI lista dependencias; politica clara (solo admin; posible bloqueo si hay docs) |
| Exposicion de datos de clientes en decisiones | Solo BO autenticado; considerar enmascarar telefono parcial para rol `viewer` en iteracion futura (fuera de v1 salvo compliance) |

**Rollback de codigo**: revert PR; no hay migracion obligatoria en v1.

**Rollback de datos**: no aplica (solo lecturas y CRUD sobre datos operativos; backup PITR Railway si borrado erroneo).

## Referencias

- Spec predecesora: [003 - Grafo LangGraph + retrieval hibrido](./003-langgraph-hybrid-rag-and-knowledge-restructure.md)
- Conversaciones / playground: [002](./002-agent-conversations-mirror-and-playground.md)
- Repositorios: `services/common/src/biomont_common/db/product_repository.py`, `conversation_repository.py`, `rag_repository.py`
- UI documentos actual: `services/backoffice-web/app/(dashboard)/documents/[id]/page.tsx`
