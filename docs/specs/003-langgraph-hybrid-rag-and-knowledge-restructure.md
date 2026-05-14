# 003 - Grafo LangGraph + retrieval hibrido + reestructuracion de conocimiento

## Contexto y objetivo

El agente WhatsApp opera hoy con un pipeline lineal LCEL (`services/agent/src/app/agent/rag_pipeline.py`) sobre un store unico `public.document_chunks` indexado solo por similitud coseno y filtrado por pais. El catalogo objetivo de Biomont es de ~100 productos, cada uno con tres documentos PDF (bitacora ~35 pp, ficha tecnica ~3 pp, balotario ~2 pp). Con ese volumen el pipeline actual presenta dos problemas concretos, observables en los PDFs reales (`PROTEGGO 3M y M_Bitacora.pdf`, `FT- PROTEGGO 3M -V3.pdf`, `PROTEGGO 3M y M_Balotario de preguntas.pdf`):

1. **Perdida de senal por mezcla semantica**: chunks de 500 tokens con metadata `{h1, h2, h3}` mezclan farmacocinetica, comparativas competitivas, dosificaciones y FAQ en el mismo espacio vectorial. El recall@k empeora a medida que crece el corpus.
2. **Ausencia de resolucion de entidades**: productos casi homonimos (`Proteggo M` vs `Proteggo 3M`) producen respuestas validas para el producto equivocado, lo que es **clinicamente peligroso** (ej.: el balotario afirma que solo 3M tiene estudios de seguridad en gestacion).

En paralelo, el roadmap incluye un **motor de calculo de dosis** que sera una herramienta del agente, alimentado por formulas y tablas estructuradas. Esta spec no implementa ese motor, pero deja el grafo del agente preparado como nodo placeholder, y separa fisicamente el conocimiento textual (RAG) del conocimiento estructurado (productos + alias) para no tener que reescribir el agente cuando se incorpore.

Objetivo: reducir el ruido del retrieval con chunking guiado por la estructura conocida de los PDFs, sumar BM25 + filtros pre-retrieval, materializar productos como entidad de primera clase con aliases para resolucion deterministica, indexar el balotario como FAQ con retrieval directo, y reemplazar la cadena LCEL por un grafo LangGraph con nodos diferenciados que admita la futura tool `Calculator`.

## Alcance / fuera de alcance

### En alcance

- **Migracion de schema** (`migrations/004_*.sql`): nuevas tablas `products`, `product_aliases`, `document_sections`, `knowledge_chunks` (reemplazo de `document_chunks` con columnas discriminantes + `tsv tsvector`), `faq_entries`, `conversation_state`. Extension `pg_trgm` instalada.
- **Tipos de documento**: enum `document_kind` (`ficha_tecnica`, `bitacora`, `balotario`) agregado a `documents`, y FK opcional `documents.product_id`.
- **ETL determinista por seccion**: nuevo `StructuredMarkdownChunker` que detecta cabeceras numeradas (`1.`, `1.1`, `1°`, `1.1°`) y separa secciones antes del split por tokens. Cada seccion produce uno o mas chunks con metadata enriquecida (`document_kind`, `section_type`, `subsection_type`, `page`, `contains_table`, `topic`).
- **Extractor LLM acotado para FAQ del balotario**: detecta pares pregunta-respuesta y los persiste en `faq_entries` con `normalized_question`, embedding propio y FK a `product_id`. El resto del documento balotario tambien se chunkifica para fallback.
- **Embeddings parametrizables**: `OPENAI_EMBEDDINGS_DIM` se mueve a settings con default `1536`. Default sigue siendo `text-embedding-3-small`. El cambio a `text-embedding-3-large` queda como configuracion futura sin migracion de datos en esta spec.
- **Retrieval hibrido**: nueva ruta SQL que combina coseno (`<=>`) sobre `embedding` y `ts_rank_cd` sobre `tsv` con fusion por **score ponderado** (`vector_weight * vec_score + bm25_weight * bm25_score`, defaults `0.7 / 0.3`, configurables por env).
- **Filtros pre-retrieval**: por `product_id` (resuelto antes), `document_kind`, `section_type` (cuando aplica), pais habilitado del RTC. Filtros sobre columnas dedicadas, no JSONB libre.
- **Grafo LangGraph** en `services/agent`: nodos `IntentClassifier`, `ProductResolver`, `MetaFilter`, `FAQRetriever`, `HybridRetriever`, `Answerer`, `StateUpdater`. Nodo `Calculator` declarado como placeholder con interfaz tipada pero sin implementacion (lanza `NotImplementedError` controlado, no se enruta hacia el en v1).
- **ProductResolver deterministico**: pg_trgm (`similarity()`) + matching exacto sobre `product_aliases`. Sin LLM. Devuelve `ambiguous` con candidatos si la diferencia entre top-1 y top-2 es menor a un umbral, en cuyo caso el agente repregunta.
- **FAQ retrieval directo**: si la query matchea una `faq_entry` por trigram + embedding por encima de umbral, el grafo cortocircuita y responde con la entrada canonica.
- **`conversation_state`**: tabla 1:1 con `conversations` que persiste `current_product_id`, `current_topic`, `current_species`, `last_intent`, `updated_at`. La actualiza el nodo `StateUpdater` al final de cada turno con valores deterministicos (los que ya resolvieron los nodos previos).
- **Bootstrap de `products`**: script idempotente `services/backoffice-api/scripts/bootstrap_products.py` que lee `documents.product_name` distinct y crea filas en `products` + aliases minimos (nombre + variantes obvias por regex). Operacion manual posterior queda fuera de alcance.
- **Reingesta one-shot**: comando administrativo `POST /api/admin/documents/{id}/reingest` (solo `admin`) que vuelve a procesar un documento ya validado contra el ETL nuevo, borra sus chunks viejos y los reemplaza. La migracion incluye dejar la tabla vieja `document_chunks` intacta hasta que termine la reingesta, y un toggle de feature flag en el agente para conmutar a `knowledge_chunks`.
- **Observabilidad por nodo del grafo**: logs estructurados con `event=node_started|node_completed`, `node`, `latency_ms`, `request_id`, `conversation_id`. Decisiones del agente (`agent_decisions`) reciben un campo nuevo `graph_trace jsonb` con el camino de nodos atravesados.
- **Golden set y evaluacion**: ver Plan de pruebas.

### Fuera de alcance

- Motor de calculo de dosis (queda como nodo placeholder con interfaz).
- Tablas clinicas estructuradas (`protocols`, `protocol_steps`, `parasites`, `product_indications`, `competitors`, `competitive_arguments`, `scientific_claims`, `references`). Schema tentativo se incluye como **ADR de fase 2** al final de esta spec, sin crear las tablas.
- Extraccion automatica de rangos de dosis, parasitos, especies y claims (los chunks marcan `contains_dose=true` o `contains_table=true` pero no se extrae a columnas).
- Reranker con cross-encoder (cohere/openai). Queda como feature flag desactivado en codigo, sin contrato firme en esta spec.
- Resumidor LLM de la conversacion (la memoria de esta spec es deterministica).
- Migracion del modelo de embeddings a `3-large`.
- UI nueva en backoffice para gestionar productos/aliases. El bootstrap es por script; mantener desde BO queda para spec siguiente.
- Tablas de dosificacion por peso de la ficha tecnica extraidas a estructura relacional.
- Replicacion del orchestrator existente para el camino "no WhatsApp" (sigue la logica de spec 002).

## Requisitos funcionales

### Modelo de datos y migracion

- **RF-1**: Existe tabla `products` (id uuid pk, name, brand default `'Biomont'`, duration_type text nullable, description text nullable, country_iso char(2) nullable, created_at, updated_at). Constraint `UNIQUE (lower(name), country_iso)` con `country_iso` null tratado como global.
- **RF-2**: Existe tabla `product_aliases` (id, product_id fk, alias text, normalized_alias text generated lower+unaccent, source text in (`name`, `manual`, `bootstrap`), confidence numeric(3,2) default `1.0`). Indice trigram GIN sobre `normalized_alias`.
- **RF-3**: `documents` recibe columnas `kind public.document_kind NOT NULL DEFAULT 'bitacora'` y `product_id uuid NULL REFERENCES products(id) ON DELETE SET NULL`. Backfill: documentos existentes quedan `kind='bitacora'` y `product_id=NULL` (los re-asocia el bootstrap).
- **RF-4**: Existe tabla `document_sections` (id, document_id fk, section_index int, parent_section_id fk nullable, section_number text, section_title text, section_kind text, page_start int, page_end int, raw_text text, created_at). Indice `(document_id, section_index)`.
- **RF-5**: Existe tabla `knowledge_chunks` (id, document_id fk, section_id fk, product_id fk nullable, kind document_kind not null, section_type text, subsection_type text nullable, topic text nullable, content text, token_count int, contains_table bool default false, contains_dose bool default false, species text[] default '{}', metadata jsonb default '{}', embedding vector(1536), tsv tsvector generated, created_at). Indices: HNSW sobre `embedding` (cosine), GIN sobre `tsv`, btree `(product_id, kind)`, btree `(kind, section_type)`.
- **RF-6**: Existe tabla `faq_entries` (id, product_id fk nullable, document_id fk, question text, normalized_question text generated, answer text, embedding vector(1536), tsv tsvector generated, source_page int nullable, created_at). Indices trigram GIN sobre `normalized_question`, GIN sobre `tsv`, HNSW sobre `embedding`.
- **RF-7**: Existe tabla `conversation_state` (conversation_id pk + fk a conversations on delete cascade, current_product_id fk nullable, current_topic text nullable, current_species text nullable, last_intent text nullable, updated_at). Default vacio al crearse una conversacion (trigger o `INSERT ... ON CONFLICT` desde el grafo).

### ETL y bootstrap

- **RF-8**: `MarkdownChunker` actual se mantiene para compatibilidad pero el ingest nuevo usa `StructuredMarkdownChunker` que:
  - Detecta cabeceras `^\d+\.\s+[A-ZA-U ]+$` (ficha tecnica), `^\d+°\s+` y `^\d+\.\d+\s+` (bitacora), `^•\s+¿.+\?$` (balotario).
  - Asocia cada chunk a un `section_id` recien creado.
  - Marca `contains_table=true` si detecta filas con patron `[A-Z][a-z]+\s+\d` repetido o frases tipo "Peso corporal" en tabla de dosis.
  - Marca `contains_dose=true` si el chunk contiene patrones `\d+\s*(-\s*\d+)?\s*mg/kg`, `\d+\s*(-\s*\d+)?\s*mg`, `c/\d+\s*h`, frecuencias.
  - Falla con error explicito si el parser no detecta ninguna seccion esperada en un documento con `kind` declarado (el documento queda `failed` con razon `etl_no_sections_detected`).
- **RF-9**: Si el documento es `kind='balotario'`, un paso adicional de extractor LLM identifica pares pregunta-respuesta y los inserta en `faq_entries`. El mismo balotario tambien se chunkifica normalmente (fallback). El extractor recibe el markdown completo y devuelve JSON estructurado con esquema fijo. Modelo: `gpt-4o-mini` con `response_format=json_schema`, timeout 30 s, retry hasta 2 veces. Si falla, el documento queda `validated` igual pero con `classification.faq_extraction_failed=true` para reproceso manual.
- **RF-10**: Comando `bootstrap_products.py` (entrypoint en `services/backoffice-api/scripts/`) corre idempotente: lee `documents.product_name` distinct no nulo, crea fila en `products` si no existe (matching por `lower(name) + country_iso`), crea aliases base (nombre original; variantes generadas por regex: `Proteggo 3M` -> aliases `proteggo 3m`, `proteggo trimestral`, `proteggo 3 meses`; `Proteggo M` -> aliases `proteggo m`, `proteggo mensual`, `proteggo 1 mes`). Reasocia `documents.product_id` por match exacto. No borra nada. Se ejecuta una sola vez post-migracion.
- **RF-11**: Endpoint `POST /api/admin/documents/{id}/reingest` (auth admin del BO) marca el documento como `processing`, borra sus chunks en `knowledge_chunks` (y `document_chunks` si quedaran), borra sus secciones, vuelve a correr el ETL nuevo. Si falla, documento queda `failed`. Solo reingesta `validated` o `failed`, no `draft`.

### Grafo del agente

- **RF-12**: El agente reemplaza `RagPipeline.run` por un grafo LangGraph compilado al startup. Nodos minimos: `IntentClassifier`, `ProductResolver`, `MetaFilter`, `FAQRetriever`, `HybridRetriever`, `Answerer`, `StateUpdater`. Nodo `Calculator` registrado como placeholder con interfaz `class Calculator(BaseNode): def run(state) -> NotImplementedError`. No se enruta hacia el en v1.
- **RF-13**: `IntentClassifier` clasifica el ultimo mensaje del usuario en una taxonomia cerrada: `dosage_question`, `clinical_protocol`, `comparison_with_competitor`, `safety_question`, `faq`, `chitchat`, `out_of_scope`. Modelo: `gpt-4o-mini` con few-shot y `response_format=json_schema`. Cache por hash de mensaje + system_prompt_version durante la conversacion activa.
- **RF-14**: `ProductResolver` recibe el mensaje + `current_product_id` del `conversation_state`. Estrategia:
  1. Match exacto contra `product_aliases.normalized_alias` (lowercase + unaccent del query).
  2. Si no, `pg_trgm.similarity()` sobre `normalized_alias` con `LIMIT 5`.
  3. Si top-1 similarity >= `PRODUCT_RESOLVER_THRESHOLD` (default `0.55`) **y** la diferencia top-1 - top-2 >= `PRODUCT_RESOLVER_MARGIN` (default `0.10`): resolved.
  4. Si no, devolver `ambiguous` con candidatos.
  5. Si el query no contiene mencion de producto pero existe `current_product_id` y la conversacion sigue activa (mismo `conversation_id`), heredar ese producto con marca `inherited_from_state=true`.
- **RF-15**: Cuando el resolver devuelve `ambiguous`, el grafo no llama al LLM general: responde con un mensaje de aclaracion (`"Estoy entre {A} y {B}, ¿podes confirmar?"`) y registra una `agent_decision` con `decision='low_confidence'` y `reasoning='ambiguous_product'`. Caso especial: si el intent es `chitchat`, el grafo salta el resolver.
- **RF-16**: `MetaFilter` compone los filtros pre-retrieval a partir de: `product_id` resuelto, `kind` heuristico segun intent (`faq` -> `kind IN ('balotario')`; `clinical_protocol` -> `kind IN ('bitacora')`; resto -> sin restriccion de kind), paises permitidos del RTC.
- **RF-17**: `FAQRetriever` corre solo si `intent='faq'` o si el primer chunk del balotario obtiene score muy alto en el retriever hibrido. Busca en `faq_entries` por trigram + embedding, fusion ponderada (mismo esquema que el general). Si top-1 supera `FAQ_DIRECT_THRESHOLD` (default `0.80` despues de la fusion), devuelve la respuesta canonica sin pasar por el LLM general y registra `decision='answered'` con `reasoning='faq_direct'`.
- **RF-18**: `HybridRetriever` ejecuta una unica query SQL que devuelve top-k (default 6) usando:
  - `vec_score = 1 - (embedding <=> :query_embedding)`
  - `bm25_score = ts_rank_cd(tsv, plainto_tsquery('spanish', :query_text))`
  - `final_score = :vector_weight * normalize(vec_score) + :bm25_weight * normalize(bm25_score)`
  - Donde `normalize` es min-max sobre el conjunto candidato preseleccionado (CTE que toma top-N por cada metrica antes de fusionar; N default 25 por canal).
  - Filtros pre-retrieval aplicados en el WHERE del CTE.
- **RF-19**: `Answerer` construye el prompt con los chunks recuperados y llama al LLM con `with_structured_output(RagAnswer)`, igual que hoy, conservando `Citation`. Idioma de la respuesta espejado al del usuario.
- **RF-20**: `StateUpdater` persiste en `conversation_state` los valores resueltos por el grafo (`current_product_id`, `current_topic = intent`, `current_species` si fue extraida del query con regex acotado; este campo es best-effort, puede quedar `NULL`). Idempotente: usa `INSERT ... ON CONFLICT (conversation_id) DO UPDATE`.
- **RF-21**: Cada decision del agente queda registrada en `agent_decisions` con `graph_trace jsonb` que lista, en orden, los nodos atravesados y su latencia. Para no romper compatibilidad, esta columna es opcional (default `'[]'`).

### Configuracion

- **RF-22**: Nuevas variables de entorno: `OPENAI_EMBEDDINGS_DIM` (default 1536), `RAG_VECTOR_WEIGHT` (default 0.7), `RAG_BM25_WEIGHT` (default 0.3), `RAG_TOP_K` (default 6), `RAG_CANDIDATE_K` (default 25), `PRODUCT_RESOLVER_THRESHOLD` (default 0.55), `PRODUCT_RESOLVER_MARGIN` (default 0.10), `FAQ_DIRECT_THRESHOLD` (default 0.80), `AGENT_USE_GRAPH` (default `true`, feature flag de corte; si `false`, el agente sigue usando el pipeline LCEL viejo contra `document_chunks`). Documentadas en `.env.example`.

## Requisitos no funcionales

- **RNF-1 Latencia**: end-to-end p95 ≤ 15 s (mismo objetivo que spec 002 RNF-1). Por nodo, presupuesto orientativo: IntentClassifier ≤ 1.5 s, ProductResolver ≤ 200 ms, HybridRetriever ≤ 600 ms, Answerer ≤ 8 s. Se mide y se reporta, no es bloqueante por nodo, si por agregado.
- **RNF-2 Determinismo donde corresponda**: ProductResolver, MetaFilter, StateUpdater son deterministicos. IntentClassifier y Answerer usan LLM, pero con `temperature` baja (0 para clasificacion, 0.1 para respuesta).
- **RNF-3 Observabilidad**: logs estructurados (`structlog`) por nodo con `event`, `node`, `latency_ms`, `request_id`, `rtc_user_id`, `conversation_id`, `intent`, `product_id`, `decision`. Logs de retrieval incluyen `top_k_scores` (lista de tuplas `(chunk_id, vec_score, bm25_score, final_score)`).
- **RNF-4 Backwards compatibility**: la spec 002 (vista espejo y playground) no debe romperse. El playground sigue invocando el mismo orchestrator, que internamente llama al grafo en lugar del pipeline LCEL.
- **RNF-5 Idempotencia**: reingesta de un documento ya validado debe ser idempotente: dos llamadas seguidas dejan el mismo resultado. El bootstrap de productos debe ser idempotente: dos ejecuciones no duplican aliases.
- **RNF-6 Seguridad**: el endpoint de reingest requiere rol `admin`. La tabla `conversation_state` no expone PII nueva (solo IDs internos). Los logs no deben volcar `content` completo de chunks (truncado a 200 caracteres).
- **RNF-7 Costo controlado**: el extractor LLM del balotario corre **una vez por documento** (no por chunk). El clasificador de intent corre **una vez por mensaje** entrante con cache. Sin reranker en v1.
- **RNF-8 Multi-tenant por pais**: los filtros pre-retrieval respetan `country_iso` permitido del RTC (semantica actual). Productos `country_iso=NULL` se consideran globales.

## Criterios de aceptacion (Given/When/Then)

### Schema y bootstrap

- **CA-1 (migracion aplicada limpia)**
  - **Given** una base con `migrations/001..003` aplicadas y la extension `vector` y `pgcrypto` instaladas,
  - **When** se aplica `migrations/004_*.sql`,
  - **Then** se crean `products`, `product_aliases`, `document_sections`, `knowledge_chunks`, `faq_entries`, `conversation_state`; la extension `pg_trgm` queda instalada; `documents.kind` y `documents.product_id` aparecen como columnas; ningun dato existente se pierde; el rollback `004_*.down.sql` revierte todo sin errores.

- **CA-2 (bootstrap idempotente)**
  - **Given** la migracion aplicada y N documentos existentes con `product_name` no nulo,
  - **When** se ejecuta `bootstrap_products.py` dos veces seguidas,
  - **Then** la cantidad de filas en `products` no cambia entre la primera y la segunda ejecucion; los aliases base no se duplican; `documents.product_id` queda poblado para los documentos cuyo `product_name` matchea exacto.

### ETL y FAQ

- **CA-3 (ETL deterministico por seccion sobre ficha tecnica)**
  - **Given** un PDF de ficha tecnica con estructura `1.` a `18.` y la flag `AGENT_USE_GRAPH=true`,
  - **When** se ingresa el documento con `kind='ficha_tecnica'` y `product_id` asignado,
  - **Then** se crean al menos 15 filas en `document_sections` (una por seccion numerada detectada) y los `knowledge_chunks` resultantes referencian la seccion correcta via `section_id`; los chunks correspondientes a la seccion "9. DOSIFICACION" tienen `contains_dose=true` y `contains_table=true`.

- **CA-4 (FAQ extraida del balotario)**
  - **Given** un PDF de balotario con N preguntas (formato `• ¿...?` seguido de respuesta),
  - **When** se ingresa con `kind='balotario'`,
  - **Then** se crean N filas en `faq_entries` con `question`, `answer`, embedding y `product_id` asignado; `documents.classification.faq_extraction_failed` no esta presente o es `false`.

- **CA-5 (fallback de FAQ si extractor LLM falla)**
  - **Given** un balotario y un mock del LLM extractor que devuelve error,
  - **When** se ingresa el documento,
  - **Then** el documento queda `validated`, los chunks del balotario existen, `classification.faq_extraction_failed=true`; el agente puede igual responder via retrieval normal del chunk.

### Grafo y resolucion de productos

- **CA-6 (regresion clinica: Proteggo M vs 3M en gestacion)**
  - **Given** productos `Proteggo M` y `Proteggo 3M` con aliases y balotario indexados,
  - **When** un usuario consulta `"puedo usar Proteggo M en gestacion"`,
  - **Then** el ProductResolver resuelve a `Proteggo M` (no 3M); el FAQRetriever encuentra la pregunta del balotario; la respuesta refleja que `Proteggo M` **no tiene estudios** que comprueben su seguridad en gestacion; en el `agent_decisions.graph_trace` figuran los nodos `IntentClassifier`, `ProductResolver`, `FAQRetriever`, `Answerer`.

- **CA-7 (resolver ambiguo dispara repregunta)**
  - **Given** dos productos con nombres similares y umbral `PRODUCT_RESOLVER_MARGIN=0.10`,
  - **When** un usuario manda un mensaje generico (`"que dosis le doy"`) sin contexto previo,
  - **Then** el grafo devuelve un mensaje de aclaracion listando los candidatos posibles; no se invoca al `Answerer`; se registra `agent_decisions.decision='low_confidence'` con `reasoning='ambiguous_product'`.

- **CA-8 (herencia desde `conversation_state`)**
  - **Given** una conversacion activa con `current_product_id` = id de `Proteggo 3M`,
  - **When** el siguiente mensaje del mismo RTC dice `"y en lactancia?"` sin nombrar producto,
  - **Then** el ProductResolver hereda `Proteggo 3M`; el `graph_trace` indica `inherited_from_state=true`; la respuesta cita el balotario de 3M.

### Retrieval hibrido

- **CA-9 (BM25 mejora sobre coseno puro en query lexica)**
  - **Given** un golden set con al menos una consulta lexica (`"que es fluralaner"`) y otra semantica (`"que mata las pulgas"`),
  - **When** se compara el recall@5 del retriever hibrido vs el retriever solo-coseno (`AGENT_USE_GRAPH=false`),
  - **Then** el hibrido tiene recall@5 ≥ al coseno puro en al menos el 80 % de las queries del set; el delta promedio no es menor a 0 pp.

- **CA-10 (filtros pre-retrieval respetan pais)**
  - **Given** dos productos del mismo nombre en dos paises distintos y un RTC habilitado solo para PE,
  - **When** una consulta resuelve a ese producto,
  - **Then** el retriever solo devuelve chunks de documentos con `country_iso='PE'` o `NULL`.

### Memoria, observabilidad, reingesta

- **CA-11 (StateUpdater idempotente)**
  - **Given** una conversacion sin estado previo y un primer mensaje resuelto,
  - **When** termina el turno,
  - **Then** existe una fila en `conversation_state` con `current_product_id` poblado; un segundo turno actualiza la misma fila (no inserta una nueva); `updated_at` cambia.

- **CA-12 (graph_trace registrado)**
  - **Given** un turno completo del agente que pasa por todos los nodos,
  - **When** termina,
  - **Then** la fila en `agent_decisions` tiene `graph_trace` con la lista ordenada de nodos atravesados y su latencia individual, y `top_similarity` se mantiene como el final_score del top-1 (no el cos-only).

- **CA-13 (reingesta limpia y atomica)**
  - **Given** un documento `validated` con chunks viejos en `document_chunks` y eventualmente en `knowledge_chunks`,
  - **When** un admin invoca `POST /api/admin/documents/{id}/reingest`,
  - **Then** al terminar OK, el documento queda `validated`, todos sus chunks anteriores estan reemplazados, las secciones se regeneran, los counts coinciden; si el ETL falla a mitad, el documento queda `failed` y los chunks viejos se conservaron (transaccion).

### Feature flag y compatibilidad

- **CA-14 (corte por flag)**
  - **Given** `AGENT_USE_GRAPH=false` en el agente,
  - **When** llega un mensaje WhatsApp,
  - **Then** el agente sigue usando el pipeline LCEL viejo y `document_chunks`; ninguna fila se escribe en `conversation_state` ni en `knowledge_chunks` por consulta; `graph_trace` queda `'[]'`.

- **CA-15 (playground spec 002 sigue funcionando)**
  - **Given** la spec 002 desplegada y `AGENT_USE_GRAPH=true`,
  - **When** un operador del BO envia un mensaje desde el playground,
  - **Then** el flujo del playground (no reenvio por WhatsApp, transcript unificado) sigue funcionando contra el grafo nuevo, sin regresion en CA-2/CA-4 de la spec 002.

## Diseno tecnico

### Diagrama del grafo

```
            +-----------------------+
   query -->| IntentClassifier      |
            +-----------+-----------+
                        |
                        v
            +-----------------------+
            | ProductResolver       |---ambiguous--> repreguntar (decision=low_confidence)
            +-----------+-----------+
                        |
                        v
            +-----------------------+
            | MetaFilter            |
            +-----------+-----------+
                        |
                        v
            +-----------------------+
            | (route by intent)     |
            +---+----------+--------+
                |          |
                | faq      | resto
                v          v
        +--------------+ +----------------+
        | FAQRetriever | | HybridRetriever|
        +-----+--------+ +--------+-------+
              | direct           |
              | (>= 0.80)        |
              v                  v
        +-------------------------+
        | Answerer (LLM struct)   |
        +-----------+-------------+
                    |
                    v
        +-------------------------+
        | StateUpdater            |
        +-------------------------+
                    |
                    v
                 response

        + nodo Calculator placeholder (no enrutado en v1)
```

### Archivos impactados (previstos)

- `migrations/004_knowledge_restructure.sql` + `.down.sql`.
- `services/common/src/biomont_common/db/`:
  - `rag_repository.py`: nuevo metodo `search_hybrid_chunks(...)`, mantiene `search_similar_chunks` para flag-off.
  - Nuevo `product_repository.py` (CRUD basico + lookup por alias).
  - Nuevo `faq_repository.py`.
  - Nuevo `conversation_state_repository.py`.
- `services/common/src/biomont_common/integrations/text_splitter.py`: agrega `StructuredMarkdownChunker` (no reemplaza `MarkdownChunker`, lo extiende).
- `services/common/src/biomont_common/integrations/faq_extractor.py`: nuevo, llama al LLM con `json_schema` y devuelve lista de pares Q-A.
- `services/common/src/biomont_common/schemas/`: nuevos `Product`, `ProductAlias`, `FaqEntry`, `KnowledgeChunk`, `ConversationState`, `GraphTrace`.
- `services/common/src/biomont_common/settings.py`: agrega `RagSettings` con los nuevos defaults.
- `services/agent/src/app/agent/`:
  - `rag_pipeline.py` se conserva para el camino flag-off.
  - Nuevo paquete `graph/` con `nodes/` (`intent.py`, `product_resolver.py`, `meta_filter.py`, `faq_retriever.py`, `hybrid_retriever.py`, `answerer.py`, `state_updater.py`, `calculator.py`) y `graph.py` que compone el `StateGraph` LangGraph.
  - `orchestrator.py`: lee el flag y enruta a grafo o pipeline.
- `services/backoffice-api/src/app/`:
  - `services/etl_pipeline.py`: usa `StructuredMarkdownChunker` y `faq_extractor` segun `kind`.
  - `api/documents_router.py`: agrega endpoint `POST /api/admin/documents/{id}/reingest`.
  - `db/document_repository.py`: persistencia de `document_sections`, FK a `product_id`, soporte para `kind`.
- `services/backoffice-api/scripts/bootstrap_products.py`: nuevo.
- `.env.example`: agrega variables RF-22.
- Tests: `services/agent/tests/test_graph_*`, `services/common/tests/test_structured_chunker.py`, `services/common/tests/test_hybrid_retrieval.py`, `services/backoffice-api/tests/test_reingest_endpoint.py`, `services/agent/tests/test_eval_golden_set.py`.

### Decisiones de diseno relevantes

- **Por que LangGraph y no seguir con LCEL**: necesitamos enrutamiento condicional (FAQ vs hibrido, ambiguous vs resolved), nodo paralelo opcional (Calculator), y trazabilidad por nodo. LCEL hace esto a costa de helpers ad-hoc y vuelve los tests opacos. LangGraph entrega `StateGraph` con tipado y persistencia de estado opcionales.
- **Por que columnas dedicadas y no todo JSONB**: el filtro de retrieval con JSONB libre escala mal y obliga a indices GIN sobre `metadata`. Las dimensiones de filtrado estables (`kind`, `section_type`, `product_id`, `contains_dose`, `species`) van a columnas con indices btree o GIN especificos.
- **Por que no reranker en v1**: agrega latencia (>500 ms p95) y costo recurrente. Sin baseline cuantitativo no podemos justificarlo. Queda como feature flag.
- **Por que `score ponderado` y no RRF**: RRF es buena cuando los rankings son comparables pero las escalas son distintas. Aca tenemos escalas controladas (cos in [0,1], ts_rank_cd normalizable). El score ponderado es mas legible y permite a quien opera el sistema mover el peso facilmente segun observe.
- **Por que extraer FAQ con LLM y no con regex**: el formato del balotario es `• ¿...?\n<respuesta multilinea>` y a veces la respuesta incluye sub-bullets. Un regex robusto es factible pero fragil; el costo de un solo llamado LLM por documento (no por chunk) es marginal y la spec lo aisla con response_format estricto + fallback a chunks normales si falla.
- **Por que no extraer dosis ahora**: el motor de calculo (tool) ya va a tener su propia fuente de verdad estructurada (que se define en la spec del motor). Extraer dosis con LLM ahora a una tabla intermedia genera deuda: o se descarta cuando llegue el motor, o se duplica.

### Notas de implementacion del retrieval hibrido (referencia SQL)

```sql
WITH vec AS (
    SELECT id, embedding <=> :query_emb AS vec_dist, kind, product_id
    FROM public.knowledge_chunks
    WHERE (:product_id IS NULL OR product_id = :product_id)
      AND (:kinds IS NULL OR kind = ANY(:kinds::document_kind[]))
    ORDER BY embedding <=> :query_emb
    LIMIT :candidate_k
),
bm AS (
    SELECT id, ts_rank_cd(tsv, plainto_tsquery('spanish', :query_text)) AS bm_score, kind, product_id
    FROM public.knowledge_chunks
    WHERE (:product_id IS NULL OR product_id = :product_id)
      AND (:kinds IS NULL OR kind = ANY(:kinds::document_kind[]))
      AND tsv @@ plainto_tsquery('spanish', :query_text)
    ORDER BY bm_score DESC
    LIMIT :candidate_k
),
unioned AS (
    SELECT id, 1 - vec_dist AS vec_score, NULL::real AS bm_score FROM vec
    UNION
    SELECT id, NULL::real, bm_score FROM bm
),
agg AS (
    SELECT id,
           MAX(vec_score) AS vec_score,
           MAX(bm_score)  AS bm_score
    FROM unioned
    GROUP BY id
),
norm AS (
    SELECT id,
           COALESCE((vec_score - MIN(vec_score) OVER ()) /
                    NULLIF(MAX(vec_score) OVER () - MIN(vec_score) OVER (), 0), 0) AS vec_n,
           COALESCE((bm_score  - MIN(bm_score)  OVER ()) /
                    NULLIF(MAX(bm_score)  OVER () - MIN(bm_score)  OVER (), 0), 0) AS bm_n
    FROM agg
)
SELECT c.id, c.content, c.metadata, c.product_id, c.kind,
       (:vec_w * n.vec_n + :bm_w * n.bm_n) AS final_score
FROM norm n
JOIN public.knowledge_chunks c ON c.id = n.id
JOIN public.documents d ON d.id = c.document_id
WHERE d.status = 'validated'
  AND (d.country_iso IS NULL OR d.country_iso = ANY(:countries::char(2)[]))
ORDER BY final_score DESC
LIMIT :top_k;
```

Notas: este SQL es ilustrativo; la implementacion final puede preferir CTE materializadas o un `RIGHT JOIN` con `LATERAL` para evitar la doble lectura. Las ventanas para normalizacion estan acotadas al universo top-N (CTE `vec` y `bm`), no a toda la tabla.

## Migraciones necesarias

`Migraciones necesarias: si`

- Script: `migrations/004_knowledge_restructure.sql` (+ `004_knowledge_restructure.down.sql`).
- Contenido principal:
  - `CREATE EXTENSION IF NOT EXISTS pg_trgm;`
  - `CREATE TYPE public.document_kind AS ENUM ('ficha_tecnica', 'bitacora', 'balotario');`
  - `CREATE TABLE products`, `product_aliases`.
  - `ALTER TABLE documents ADD COLUMN kind public.document_kind NOT NULL DEFAULT 'bitacora';`
  - `ALTER TABLE documents ADD COLUMN product_id uuid REFERENCES products(id) ON DELETE SET NULL;`
  - `CREATE TABLE document_sections`, `knowledge_chunks`, `faq_entries`, `conversation_state`.
  - Indices: HNSW (`vector_cosine_ops`), GIN (`tsv`), GIN trigram (`gin_trgm_ops`) sobre `normalized_alias` y `normalized_question`.
  - Triggers `set_updated_at` sobre las tablas que lo necesiten.
- La migracion no toca `document_chunks` ni `documents.classification` para no perder el camino flag-off.
- `004_*.down.sql` revierte en orden inverso (drop de FKs, drop de tablas nuevas, drop de columnas nuevas en `documents`, drop del tipo enum, drop de la extension `pg_trgm` solo si fue creada por esta migracion - usar `DROP EXTENSION IF EXISTS pg_trgm;` con comentario de advertencia).

### Evidencia de estructura actual

Snapshot tomado con `psql "$DATABASE_URL"` (Railway, base `railway`, PostgreSQL 18.3) en el momento de redactar la spec:

**Extensiones instaladas**: `pgcrypto@1.4`, `plpgsql@1.0`, `vector@0.8.2`. `pg_trgm` **no esta presente** (la migracion 004 la crea).

**Tablas existentes en `public`**: `agent_decisions`, `bo_audit_log`, `bo_users`, `conversations`, `countries`, `document_chunks`, `documents`, `messages`, `rtc_user_countries`, `rtc_users`, `system_prompts`, `tickets`. No existen `products`, `product_aliases`, `document_sections`, `knowledge_chunks`, `faq_entries`, `conversation_state`.

**Enums existentes**: `agent_decision_kind`, `bo_role`, `document_status`, `message_role`, `ticket_status`, `ticket_type`. No existe `document_kind`.

**`documents` columnas** (todas presentes; FK `country_iso → countries.iso2`):
`id uuid PK`, `title text NN`, `product_name text NULL`, `country_iso char(2) NULL`, `language char(2) NN default 'es'`, `status document_status NN default 'draft'`, `source_filename text NULL`, `content_sha256 text NULL`, `markdown text NULL`, `classification jsonb NN default '{}'`, `uploaded_by uuid NULL`, `validated_by uuid NULL`, `validated_at timestamptz NULL`, `created_at timestamptz NN`, `updated_at timestamptz NN`. Indices: `documents_pkey`, `idx_documents_country`, `idx_documents_status`, `uq_documents_content_sha` (parcial sobre `content_sha256 IS NOT NULL`).

**`document_chunks` columnas**: `id uuid PK`, `document_id uuid NN`, `chunk_index int NN`, `content text NN`, `token_count int NN`, `metadata jsonb NN`, `embedding vector NN`, `created_at timestamptz NN`. Vector dim verificado = `1536`. Indices: `document_chunks_pkey`, `document_chunks_document_id_chunk_index_key` (UNIQUE), `idx_document_chunks_document`, `idx_document_chunks_embedding_hnsw` (HNSW cosine).

**Counts pre-migracion**: `documents=4`, `documents_validated=2`, `document_chunks=99`. Distinct `product_name`: `'manu'`, `'Protego 3M'`, `'test'` (datos de prueba; la migracion no asume nada sobre estos valores).

### Notas operativas

- Conexion validada con `psql "$DATABASE_URL"` desde `.env` local. Railway CLI puede o no estar autenticado; no es bloqueante mientras `DATABASE_URL` sea valido.
- La migracion se aplica con `railway run ./scripts/apply_migration.sh 004` (transaccion unica, `ON_ERROR_STOP`) o equivalente con `psql "$DATABASE_URL" -1 -f migrations/004_*.sql --set ON_ERROR_STOP=on`.

## Plan de pruebas

### Unitarios

- `test_structured_chunker.py`: parsing de ficha tecnica, bitacora y balotario reales (fixtures = los tres PDFs ya convertidos a markdown), verificando numero minimo de secciones, marcas `contains_table`/`contains_dose` y `section_type`.
- `test_faq_extractor.py`: mock del LLM con respuestas fijas; valida que se persiste el set esperado y que la falla del LLM no rompe el ingest.
- `test_product_resolver.py`: matriz de queries reales (`"el de 3 meses"`, `"el verde"`, `"proteggo 3M"`, `"un proteggo"`) vs candidatos esperados.
- `test_hybrid_retrieval.py`: stub del pool con datos sembrados; verifica fusion con `vector_weight=1, bm25_weight=0` (debe coincidir con coseno) y con `0, 1` (debe coincidir con BM25).
- `test_state_updater.py`: idempotencia y poblamiento de campos.
- `test_intent_classifier.py`: con mock LLM, valida que respuestas no validas devuelven `out_of_scope` por defecto.

### Integracion y HTTP

- `test_graph_integration.py`: ejecuta el grafo completo con mocks de LLM/embeddings, sobre fixtures sembradas en una BDD efimera, validando `agent_decisions.graph_trace`.
- `test_reingest_endpoint.py`: auth admin requerida; documento `validated` se reingesta limpio; documento `draft` rechaza la operacion; rollback si el ETL falla.
- `test_orchestrator_flag.py`: con `AGENT_USE_GRAPH=false` el agente usa el pipeline LCEL viejo (no toca tablas nuevas).

### Evaluacion (golden set)

- Nuevo directorio `services/agent/tests/eval/`:
  - `golden_set.yaml` con ≥30 preguntas curadas, cada una con: `query`, `rtc_country`, `expected_product`, `expected_intent`, `expected_chunk_ids` (lista opcional), `expected_faq_id` (opcional), `forbidden_products` (regresion clinica).
  - Comando `pytest -m eval` que corre contra una BDD efimera sembrada con los tres PDFs reales del corpus base.
  - Metricas calculadas: `product_resolver_accuracy`, `intent_accuracy`, `recall@5_vector`, `recall@5_hybrid`, `faq_direct_rate`.
  - Baseline guardado en `services/agent/tests/eval/baseline.json` (commit inicial = primera corrida del grafo nuevo).
  - **CI bloquea** si cualquiera de esas metricas regresa mas de **5 puntos porcentuales** respecto al baseline. Mejoras siempre aceptadas; el baseline se actualiza manualmente en PR aparte.
- El golden set incluye obligatoriamente: una variante de la regresion clinica (CA-6), una pregunta heredada por estado (CA-8), una consulta lexica pura y una semantica pura (CA-9), una resolucion ambigua (CA-7).

### Mocks

- LLM (Chat + Extractor + Classifier) y Embeddings se mockean con `MagicMock` siguiendo la politica de `.cursor/rules/testing-policy-python.mdc`: en CI no se llama a OpenAI real.
- WhatsApp client se mockea como en la spec 002.

## Observabilidad

- Logs estructurados (structlog) por nodo del grafo:
  - `event=node_started`, `event=node_completed`, `event=node_error` con `node`, `latency_ms`, `request_id`, `conversation_id`, `rtc_user_id`.
- Eventos de negocio:
  - `event=intent_classified` con `intent`, `cache_hit`.
  - `event=product_resolved` con `product_id`, `confidence`, `inherited_from_state`.
  - `event=product_ambiguous` con candidatos top-N.
  - `event=faq_direct_hit` con `faq_id`, `final_score`.
  - `event=hybrid_retrieved` con `top_k_scores` (truncado a top-5 `(chunk_id, vec_score, bm25_score, final_score)`).
  - `event=state_updated` con `current_product_id`, `current_topic`.
  - `event=reingest_started`, `event=reingest_completed`, `event=reingest_failed` (admin endpoint).
- Metricas (a futuro, si existe stack; si no, logs agregables):
  - Contador `agent_decisions.decision` por dia.
  - Histograma de `latency_ms` por nodo.
  - Contador de `product_ambiguous` (proxy de calidad de aliases).
- Trazas: `agent_decisions.graph_trace jsonb` permite reconstruir el camino de cada turno sin pegar logs.

## Riesgos y rollback

| Riesgo | Mitigacion |
| --- | --- |
| Reingesta masiva impacta latencia en horario operativo | Ejecutar la reingesta en lote desde un job admin, no en linea; documentar ventana; mantener `AGENT_USE_GRAPH=false` hasta que termine la reingesta. |
| ProductResolver falla en silencio y el agente responde sobre el producto equivocado | CA-6 y CA-7 cubren la regresion. Umbrales conservadores. Repregunta como decision por defecto en bajo margen. Golden set obligatorio. |
| Extractor FAQ devuelve preguntas mal formadas | `response_format=json_schema`; fallback a chunks normales del balotario (CA-5); marca `faq_extraction_failed` para reproceso. |
| Costo del clasificador de intent crece con volumen | Cache por hash de mensaje + system_prompt_version mientras la conversacion sigue activa; modelo `gpt-4o-mini`. |
| Migracion `004_*` falla a mitad | `BEGIN/COMMIT` envolvente; `apply_migration.sh` aborta al primer error; `004_*.down.sql` revierte tablas nuevas. |
| Cambio de embedding model en el futuro deja chunks viejos no comparables | Esta spec no migra modelo; cuando se cambie, requerir reingesta total como prerrequisito (documentado en ADR de fase 2). |
| `tsvector` en espanol con stopwords corta queries cortas | Probar con `plainto_tsquery('spanish', ...)` y `simple` como fallback si la query es muy corta; medir con golden set. |
| Filtros por `country_iso` rompen consultas globales si el RTC no tiene paises asociados | Mantener semantica actual: `NULL` se considera global, RTC sin paises ve solo globales. Tests cubren CA-10. |
| Reranker prematuro sumaria latencia y costo sin baseline | Reranker queda como feature flag desactivado; spec proxima si los numeros del golden set lo justifican. |

### Rollback

1. Activar `AGENT_USE_GRAPH=false` en el agente (toggle inmediato).
2. Revertir despliegue de `services/agent` y `services/backoffice-api`.
3. Ejecutar `railway run ./scripts/apply_migration.sh 004 --down` para revertir el schema. Esto destruye datos en `knowledge_chunks`, `faq_entries`, `document_sections`, `conversation_state`, `products`, `product_aliases`. Los datos en `document_chunks` permanecen intactos (no se tocaron).
4. Si la reingesta ya habia alterado `documents.product_id` y `documents.kind`, el down las elimina; los documentos vuelven a la forma original.

## Anexo: ADR de fase 2 (informativo, no se implementa aqui)

Tablas previstas para cuando se incorpore el motor de calculo y la inteligencia comercial:

- `product_presentations(product_id, dosage_mg, weight_min, weight_max, package_color, senasa_code)`
- `parasites(common_name, scientific_name, category)`
- `product_indications(product_id, parasite_id, indication_type, evidence_level, duration_days)`
- `protocols(name, pathology, species, severity)`
- `protocol_steps(protocol_id, step_order, phase, medication_name, dosage_mgkg_min, dosage_mgkg_max, frequency_text, duration_text, notes)`
- `competitors(name, active_principles[], duration_type)`
- `competitive_arguments(source_product_id, competitor_id, category, claim, evidence)`
- `scientific_claims(product_id, claim_type, claim, source_reference, confidence)`
- `references_(citation, authors, year, source_type)` (renombrado para evitar palabra reservada)
- `dosing_ranges(product_id, indication_id, dose_mgkg_min, dose_mgkg_max, frequency, duration_days, evidence_level)`

Esquema tentativo, sujeto a la spec del motor de calculo. La spec actual deja columnas en `knowledge_chunks` (`contains_dose`, `species`, `contains_table`) que permiten localizar los chunks fuente para una futura migracion estructurada.
