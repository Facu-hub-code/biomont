# 006 - Backoffice: vinculacion producto ↔ documento (N:M)

## Contexto y objetivo

Hoy la relacion entre catalogo y corpus esta modelada como **1:N** via `documents.product_id` (FK opcional a `products`). Eso cubre el caso habitual (un producto tiene varias fichas, bitacoras y balotarios propios), pero **no** el caso operativo real en que **un mismo PDF/documento aplica a varios productos** — por ejemplo una bitacora compartida de **Proteggo M** y **Proteggo 3M** donde el contenido clinico referencia ambas presentaciones.

Consecuencias del modelo actual:

- El backoffice solo muestra **`document_count`** por producto; no lista ni edita vinculos ([spec 004](./004-backoffice-products-documents-and-agent-decisions.md) dejo el enlace cruzado como decision de diseno pendiente).
- Solo se puede asignar **un** `product_id` al subir o reingestar un documento.
- El agente filtra retrieval con `knowledge_chunks.product_id = $producto_resuelto`; un documento compartido indexado con un solo `product_id` (o `NULL`) **no aparece** cuando el usuario pregunta por el otro producto del par.

**Objetivo**: introducir una relacion **many-to-many** explicita entre `products` y `documents`, gestionable desde el backoffice, con **producto primario** opcional para compatibilidad, backfill de datos existentes, y alineacion del **retrieval del agente** para que los documentos compartidos entren en el contexto de cualquiera de los productos vinculados.

## Alcance / fuera de alcance

### En alcance

- Tabla puente **`document_products`** (`document_id`, `product_id`, `is_primary`, metadatos de auditoria).
- **Migracion 006** con backfill desde `documents.product_id` y script `.down.sql`.
- Mantener `documents.product_id` como **producto primario denormalizado** (sincronizado con la fila `is_primary = true` en `document_products`) para no romper integraciones que aun lean esa columna.
- **API backoffice** para listar, crear y eliminar vinculos; establecer/cambiar producto primario.
- **UI backoffice**:
  - En `/products/[id]`: tabla de documentos vinculados (titulo, `kind`, `status`, primario/compartido, enlaces).
  - En `/documents/[id]`: seccion **Productos vinculados** (multi-select + marcar primario).
  - En upload de documento: selector **multiple** de productos del catalogo (al menos uno recomendado; ver RF).
- Actualizar **`document_count`** en listados de productos para contar filas en `document_products` (no solo `documents.product_id`).
- **ETL / reingest**: aceptar lista de `product_ids` al crear documento; persistir vinculos y `product_id` primario; propagar `product_id` primario a `knowledge_chunks` y `faq_entries` como hoy (sin duplicar chunks por producto).
- **Agente (retrieval)**: ampliar filtros en `RagRepository.search_hybrid_chunks` y `FaqRepository.search` para incluir contenido de documentos vinculados al producto resuelto, no solo filas con `chunk.product_id` / `faq.product_id` igual.
- **Tests**: repositorio, endpoints HTTP, al menos un test de integracion agente/retrieval con documento compartido.
- **Auditoria** `bo_audit_log` en altas/bajas/cambio de primario.

### Fuera de alcance (v1)

- **Etiquetado por chunk** dentro del mismo documento (p. ej. seccion solo Proteggo M vs 3M): el vinculo es a nivel **documento**; todos los chunks del documento son visibles para todos los productos enlazados.
- **Deteccion automatica** de multi-producto desde el PDF (LLM/heuristica en ETL).
- **Duplicar** `knowledge_chunks` o embeddings por cada producto vinculado.
- Edicion del grafo LangGraph mas alla del filtro de retrieval (intent, resolver, etc. sin cambios).
- Sincronizar `documents.product_name` con multiples nombres (sigue siendo texto libre historico del upload).
- Export CSV de matriz producto-documento.

## Modelo de dominio

### Relaciones

```text
products (1) ----< document_products >---- (N) documents
                      |
                      +-- is_primary (bool, max 1 true por document_id)
```

- Un **producto** tiene **cero o muchos** documentos vinculados.
- Un **documento** tiene **cero o muchos** productos vinculados (caso compartido: 2+).
- Exactamente **cero o uno** producto **primario** por documento (`is_primary = true`). Si hay vinculos y ninguno es primario, la UI/API debe forzar eleccion al guardar (o auto-promover el primero de la lista).

### Semantica de `documents.product_id` (compatibilidad)

| Campo / tabla | Rol v1 |
|---------------|--------|
| `document_products` | Fuente de verdad de la relacion N:M |
| `documents.product_id` | **Cache del primario**; se actualiza al crear/cambiar/eliminar vinculo primario |
| `knowledge_chunks.product_id` | Copia del primario al ingestar (sin cambio de semantica) |
| `faq_entries.product_id` | Copia del primario al extraer FAQ del balotario |

Retrieval del agente para producto **P** debe considerar chunks/FAQ donde:

1. `chunk.product_id = P` (comportamiento actual), **o**
2. `chunk.document_id` pertenece a un documento con fila en `document_products` con `product_id = P`.

Asi una bitacora compartida indexada con `product_id = Proteggo_M` (primario) sigue siendo recuperable cuando el usuario pregunta por **Proteggo 3M** si ese producto esta en `document_products` para el mismo `document_id`.

## Requisitos funcionales

### Datos y migracion

- **RF-D1**: Crear tabla `public.document_products` con:
  - `id uuid PK`
  - `document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE`
  - `product_id uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE`
  - `is_primary boolean NOT NULL DEFAULT false`
  - `created_at timestamptz NOT NULL DEFAULT now()`
  - `created_by uuid NULL REFERENCES bo_users(id) ON DELETE SET NULL`
  - `UNIQUE (document_id, product_id)`
  - Indice `(product_id)` y `(document_id)`; indice unico parcial `UNIQUE (document_id) WHERE is_primary` (solo un primario por documento).
- **RF-D2**: Backfill: por cada `documents` con `product_id IS NOT NULL`, insertar fila en `document_products` con `is_primary = true`. Idempotente (`ON CONFLICT DO NOTHING`).
- **RF-D3**: Al eliminar el ultimo vinculo de un documento, poner `documents.product_id = NULL`.

### API backoffice

Prefijo coherente con spec 004 (`/products`, `/documents`).

- **RF-A1**: `GET /products/{product_id}/documents` — listado paginado de documentos vinculados (`title`, `kind`, `status`, `country_iso`, `is_primary`, `updated_at`, `document_id`).
- **RF-A2**: `POST /products/{product_id}/documents` — body `{ "document_id": uuid, "is_primary": bool? }`. Crea vinculo; si `is_primary=true`, desmarca otros y actualiza `documents.product_id`.
- **RF-A3**: `DELETE /products/{product_id}/documents/{document_id}` — quita vinculo; si era primario, recalcular primario (siguiente vinculo por `created_at` o dejar sin primario y `documents.product_id = NULL`).
- **RF-A4**: `PATCH /documents/{document_id}/products` — body `{ "product_ids": [uuid, ...], "primary_product_id": uuid | null }`. Reemplaza el conjunto de vinculos del documento (transaccion); validar que `primary_product_id` ∈ `product_ids` si ambos vienen.
- **RF-A5**: `GET /documents/{document_id}/products` — lista productos vinculados con `is_primary`, `name`, `brand`.
- **RF-A6**: Upload / reingest: aceptar `product_ids` (form multi-value o JSON) ademas de `product_id` legacy; si solo viene `product_id`, comportamiento actual + fila en `document_products`.

### UI backoffice

- **RF-U1**: Pagina producto: seccion **Documentos vinculados** con tabla paginada (RF-A1), boton **Vincular documento** (buscador por titulo/id), accion quitar vinculo, indicador **Primario**.
- **RF-U2**: Pagina documento: bloque **Productos del catalogo** con chips/lista, selector multiple, radio/check **Producto primario**, guardar via RF-A4.
- **RF-U3**: Formulario de upload: reemplazar select simple por **multi-select** de productos; primer seleccionado = primario por defecto (editable antes de enviar si la UX lo permite).
- **RF-U4**: Listado `/products`: columna **Documentos** = `COUNT(document_products)` para ese producto.
- **RF-U5**: Al eliminar producto (`DELETE /products/{id}`): modal lista documentos afectados (solo vinculos en `document_products`); politica alineada a 004 — aviso; FK `ON DELETE CASCADE` en `document_products` elimina filas puente; `documents.product_id` pasa a NULL por `ON DELETE SET NULL` en documents (ya existente).

### Agente y ETL

- **RF-R1**: `search_hybrid_chunks`: filtro de producto ampliado a union documento-vinculado (ver semantica arriba). Mantener filtros de `kind`, pais y `status = validated`.
- **RF-R2**: `FaqRepository.search`: incluir FAQ del documento si el documento esta vinculado al producto, aunque `faq_entries.product_id` sea otro primario o NULL (misma regla OR por `document_id`).
- **RF-R3**: `DocumentIngestService`: tras crear documento, insertar N filas en `document_products` y fijar primario; `knowledge_chunks` / `faq_entries` reciben `product_id` del primario unicamente.

## Requisitos no funcionales

- **RNF-1**: Operaciones de vinculacion en transaccion (especialmente PATCH que reemplaza conjunto y primario).
- **RNF-2**: Paginacion en listados (default 25, max 100).
- **RNF-3**: RBAC igual que productos en 004: mutaciones `admin` + `scientist`; lectura `viewer`.
- **RNF-4**: No re-embedir al cambiar vinculos (solo metadatos); reingest sigue siendo el camino para regenerar chunks.
- **RNF-5**: Queries de retrieval: usar `EXISTS` o `IN` sobre `document_products` indexado; evitar full scan en tablas de chunks.

## Criterios de aceptacion (Given/When/Then)

- **CA-1 (vinculo compartido)**
  - **Given** productos A y B y un documento D validado vinculado a ambos (D primario = A),
  - **When** un `scientist` guarda el vinculo desde la UI del documento,
  - **Then** existen dos filas en `document_products` y `documents.product_id = A`.

- **CA-2 (retrieval compartido)**
  - **Given** el mismo D con chunks cuyo `product_id = A`,
  - **When** el agente resuelve producto B y ejecuta HybridRetriever,
  - **Then** los chunks de D aparecen en candidatos (mismo comportamiento que si el usuario preguntara por A).

- **CA-3 (listado desde producto)**
  - **Given** al menos un documento vinculado al producto P,
  - **When** un `viewer` abre `/products/{P}`,
  - **Then** ve la tabla de documentos con titulo, kind y status (no solo el contador).

- **CA-4 (cambio de primario)**
  - **Given** D vinculado a A (primario) y B,
  - **When** se marca B como primario via PATCH documento,
  - **Then** una sola fila tiene `is_primary=true`, `documents.product_id = B`, y los chunks existentes **no** se re-embedden automaticamente (nota en UI: reingest opcional si se requiere alinear `knowledge_chunks.product_id`).

- **CA-5 (backfill)**
  - **Given** documentos legacy con `product_id` poblado antes de la migracion,
  - **When** se aplica `006_*.sql`,
  - **Then** cada uno tiene al menos una fila equivalente en `document_products` con `is_primary=true`.

- **CA-6 (conflicto duplicado)**
  - **Given** vinculo existente (D, P),
  - **When** POST duplica el mismo par,
  - **Then** API responde 409 con mensaje claro.

- **CA-7 (audit)**
  - **Given** un `admin` elimina un vinculo,
  - **When** la operacion termina,
  - **Then** hay entrada en `bo_audit_log` con `entity=document_products` o equivalente documentado.

- **CA-8 (upload multi-producto)**
  - **Given** upload con `product_ids=[A,B]` y primario A,
  - **When** el ETL termina en `validated`,
  - **Then** D tiene dos vinculos y chunks con `product_id = A`.

## Diseno tecnico

### Migracion `006_product_document_links.sql`

Evidencia de estructura actual (repo, migracion [004](../../migrations/004_knowledge_restructure.sql)):

```text
documents.product_id  uuid NULL  FK -> products(id) ON DELETE SET NULL
documents.kind        document_kind NOT NULL
idx_documents_product ON documents(product_id)

knowledge_chunks.product_id  uuid NULL  FK -> products(id)
faq_entries.product_id       uuid NULL  FK -> products(id)
```

Cambios propuestos:

```sql
CREATE TABLE public.document_products (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    UNIQUE (document_id, product_id)
);

CREATE UNIQUE INDEX uq_document_products_one_primary
    ON public.document_products (document_id)
    WHERE is_primary;

CREATE INDEX idx_document_products_product ON public.document_products (product_id);
CREATE INDEX idx_document_products_document ON public.document_products (document_id);

-- backfill INSERT ... SELECT FROM documents WHERE product_id IS NOT NULL
```

Opcional en la misma migracion: funcion/trigger `sync_documents_primary_product()` invocada desde aplicacion en v1 (preferible logica en repositorio para trazabilidad en audit).

### Backend

| Area | Archivos / cambios |
|------|-------------------|
| Repositorio | `DocumentProductRepository` en `services/common` o `backoffice-api` segun convencion; metodos list/link/unlink/set_primary/replace_for_document |
| Product admin | `product_admin_repository.py`: `document_count` via `document_products` |
| Documents | `document_repository.py`: helpers de productos vinculados |
| API | `products_router.py`, `documents_router.py` — rutas RF-A* |
| ETL | `etl_pipeline.py`: `product_ids: list[UUID]`, persistir vinculos |
| Agente | `rag_repository.py`, `faq_repository.py` — RF-R1/R2 |
| Tests | `test_products_endpoints.py`, `test_document_*`, `test_graph_pipeline.py` o test de repo RAG |

### Sketch SQL retrieval (HybridRetriever)

```sql
-- Sustituir filtro estricto:
--   AND ($4::uuid IS NULL OR c.product_id = $4)
-- Por:
AND (
    $4::uuid IS NULL
    OR c.product_id = $4
    OR EXISTS (
        SELECT 1 FROM public.document_products dp
        WHERE dp.document_id = c.document_id
          AND dp.product_id = $4
    )
)
```

Misma idea para `faq_entries` uniendo por `document_id`.

### Frontend

- `products/[id]/page.tsx`: seccion documentos + acciones server.
- `documents/[id]/page.tsx`: editor de productos vinculados.
- `documents/page.tsx`: multi-select en upload.
- Tipos API en llamadas `apiRequest`.

### Caso de uso de referencia (negocio)

| Documento | Productos vinculados | Primario | Notas |
|-----------|---------------------|----------|--------|
| Bitacora Proteggo M + 3M | Proteggo M, Proteggo 3M | Proteggo M (arbitrario) | Un solo PDF; retrieval activo para ambos |
| Ficha Proteggo 3M | Proteggo 3M | Proteggo 3M | Caso 1:N clasico |
| Balotario compartido | (futuro) varios | uno | FAQ heredan visibilidad por documento |

## Migraciones necesarias

**Migraciones necesarias: si**

- Script: `migrations/006_product_document_links.sql` + `migrations/006_product_document_links.down.sql`.
- Orden de despliegue: migracion → backfill (incluido en up) → deploy API/web/agent.
- Rollback down: elimina `document_products`; `documents.product_id` conserva ultimo valor sincronizado (aceptable).

Antes de implementar en prod, confirmar con:

```bash
railway run psql -c "
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name IN ('documents', 'products')
ORDER BY table_name, ordinal_position;
"
```

## Plan de pruebas

- **Unit / repo**: crear vinculos, unicidad, cambio de primario, backfill idempotente, sync `documents.product_id`.
- **HTTP**: RF-A1–A5 — 200, 401, 403, 404, 409; PATCH transaccional con lista vacia.
- **ETL**: ingest con dos `product_ids`; assert `document_products` y chunks con primario.
- **Agente**: fixture con documento compartido; query con producto secundario recupera chunk del documento.
- **Regresion**: documento 1:1 sigue funcionando; `document_count` en listado productos.

## Observabilidad

- Logs BO: `event=document_product_link`, `event=document_product_unlink`, `document_id`, `product_id`, `is_primary`, `actor_id`.
- Logs agente (debug): incluir en trace de HybridRetriever si el filtro uso `document_products` (opcional en payload del nodo).

## Riesgos y rollback

| Riesgo | Mitigacion |
|--------|------------|
| Desalinear `documents.product_id` y primario real | Toda mutacion pasa por repositorio unico; tests de sync |
| Chunks con `product_id` distinto al nuevo primario sin reingest | Documentar en UI; retrieval usa `document_products` ademas de columna chunk |
| Listados lentos con muchos vinculos | Indices en puente; paginacion |
| Borrar producto sorprende operadores | Modal RF-U5 con lista de documentos afectados (solo pierden vinculo, no el PDF) |

**Rollback codigo**: revert PR (API, UI, agente).

**Rollback DB**: `apply_migration.sh 006 --down` elimina tabla puente; `documents.product_id` permanece; re-aplicar 006 + backfill si se vuelve a subir.

## Referencias

- [003 - Grafo LangGraph + conocimiento](./003-langgraph-hybrid-rag-and-knowledge-restructure.md) — origen de `documents.product_id` y chunks.
- [004 - Backoffice productos y documentos](./004-backoffice-products-documents-and-agent-decisions.md) — CRUD productos; `document_count` pendiente de listado.
- `migrations/004_knowledge_restructure.sql`
- `services/common/src/biomont_common/db/rag_repository.py` — filtro actual por `product_id`
- `services/backoffice-api/src/app/services/etl_pipeline.py`
- `scripts/bootstrap_products.py` — candidato a extension futura para sugerir vinculos por `product_name` (fuera de v1)
