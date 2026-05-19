# Informe de avances — Biomont (semana corrida hasta 14 mayo 2026)

**Versión:** 1.0  
**Propósito:** corpus estructurado para alimentar un sistema de IA que arma presentaciones ejecutivas y técnicas.  
**Ámbito de fuentes:** historial Git del monorepo, especificaciones en `docs/specs/`, código activo (`services/agent`, `services/backoffice-api`, `services/backoffice-web`, `services/common`, `migrations/`) y manual extendido del backoffice. Las conversaciones Cursor no se pueden auditar línea por línea en bloque desde el repositorio; este informe sintetiza el **estado entregado** coherente con esos chats de trabajo habitual.

---

## Resumen ejecutivo (slide de apertura)

- **Biomont** une WhatsApp Cloud API para RTCs veterinarios con un agente conversacional respaldado por **RAG** sobre documentación validada (PostgreSQL **+ pgvector** en Railway).
- Esta semana se consolidó un salto grande de **motor de conocimiento**: de chunks homogéneos a un modelo **orientado por producto, tipo de PDF y secciones estructurales**, con **retrieval híbrido vectorial + BM25** y un **grafo LangGraph** con traza por turno (`graph_trace`).
- El **backoffice web** ganó **operacionalidad**: catálogo de **productos y aliases**, **auditoría de decisiones del agente**, vista enriquecida de **documento** (secciones / chunks / FAQ / legacy), y **UX asíncrona** (loading, toasts de éxito/error).
- La **cadena ETL** de PDF está anclada en **Docling** (markdown estable), endurecida con **StructuredMarkdownChunker** calibrado al corpus Biomont, extracción de **FAQ desde balotarios** (LLM una vez por documento) y **compatibilidad** con el pipeline antiguo vía tabla `document_chunks` y bandera **`AGENT_USE_GRAPH`**.

---

## Narrativa técnica de la semana (orden cronológico aproximado)

La siguiente tabla resume commits recientes observados en Git (mensajes de merge); sirve como “línea de tiempo” cuando se cuente la historia al equipo.

| Mensaje corto del commit | Tema |
| ----- | ----- |
| `feat: bootstrap Biomont v1` … | WhatsApp agent + backoffice + ETL RAG inicial |
| `feat: estado de carga en el login` | Primera UX de feedback en sesión BO |
| `feat(agent,backoffice): espejo de conversaciones y playground admin` | Spec 002: espejo estilo WhatsApp + pruebas sin enviar WhatsApp |
| `fix(rag)` / `diagramas de arquitectura` | Ajustes de metadata JSON / DX |
| **`feat(agent): grafo LangGraph + RAG híbrido + reestructura de conocimiento (spec 003)`** | Núcleo del nuevo motor |
| **`feat(backoffice): spec 004 — productos, decisiones del agente y detalle de documento`** | Nuevas secciones y APIs |
| **`feat(backoffice-web): spec 005 — feedback async, loading y toasts`** | UX de operaciones asíncronas |
| `fix(etl): robustecer StructuredMarkdownChunker` | Parsing alineado a PDFs reales |
| `chore(git): ignorar samples/ … documentar ETL` | `samples/` locales para calibración regex |
| `fix(common): operador pg_trgm correcto en búsqueda FAQ` | Corrección trigram FAQ |
| **`feat: vectorización de corpus y catálogo de productos`** | Consolidación ingest + catalogación |

Este orden ayuda en presentaciones tipo “antes → después”: de pipeline lineal único (`document_chunks`) a **esquema 004**, **dos salidas del ETL** (legacy vs `knowledge_chunks`) y **orquestador con grafo**.

---

## Nueva arquitectura de conocimiento en una frase

**Antes:** un solo tipo de fragmento (`document_chunks`) + similitud coseno.  
**Ahora:** conocimiento tipado como **producto**, **tipo documental**, **sección física**, **FAQ indexada**, **chunks enriquecidos** con filtros declarativos + **fusión ponderada embedding/BM25** y **clasificación / resolución de producto antes del retrieval**.

---

## Diseño de base de datos guiado por la estructura de PDFs Biomont

### Motivo de negocio

El corpus objetivo tiene forma repetible (~100 productos × 3 PDFs típicos: **bitácora larga**, **ficha técnica corta numerada**, **balotario Q&A corto**). El modelo viejo perdía “señal” al mezclar farmacocinética, comparativos, FAQs y dosificación en embeddings indistinguibles. También aparece riesgo clínico con productos ortográficamente cercanos (**Proteggo M vs Proteggo 3M**).

### Entidades nuevas y relaciones (conceptual)

Consultar también el glosario canónico en `docs/manual-usuario-backoffice-extendido.md`. Resumen dirigido a presentaciones:

1. **`products`**  
   Catalogación de marca de producto: nombre, marca, país opcional, duración/registro comercial donde aplique.

2. **`product_aliases`**  
   Variantes de lenguaje natural normalizadas (trigrams GIN sobre `normalized_alias`) para resolver el producto **sin LLM**.

3. **`documents`** (ampliado)  
   - `kind`: enum `document_kind`: `ficha_tecnica` | `bitacora` | `balotario`.  
   - `product_id` opcional FK a `products`; `product_name` sigue disponible como campo histórico / libre.  
   - Metadatos de ingest y validación siguen igual (`status`, `markdown`, `classification` JSON extendible).

4. **`document_sections`**  
   Materializa jerarquía detectada desde markdown (orden `section_index`, `parent_section_id`, títulos/rangos de página donde existan). Une el PDF “léxico humano” con filas físicas antes del split.

5. **`knowledge_chunks`** (motor principal moderno)  
   Fragmentos ligados a `section_id`, `kind`, tipos/sección (`section_type`, `subsection_type`), marcadores **`contains_table`**, **`contains_dose`**, arreglos `species` cuando aplique; **embedding** `vector(1536)` + columna **`tsv` tsvector** generada para BM25 en español.

6. **`faq_entries`**  
   QA extraída del balotario con embeddings y `tsvector` propios; habilita “atajo” de respuesta cuando el grafo encuentra alta confianza.

7. **`conversation_state`** (1:1 con `conversations`)  
   Memoria operativa deterministico-técnica: producto vigente del hilo, intención/“tema” del último turno, especie best-effort, etc.; actualizada al finalizar el grafo.

8. **`agent_decisions`** (enriquecida)  
   Registro por turno: decisión (`answered`, `low_confidence`, `no_match`, …), **`retrieved`**, **`graph_trace`** (lista JSON de nodos con latencias y payloads colapsables en UI).

9. **`document_chunks` (legacy)**  
   Persiste coexistencia hasta reingestar o para `AGENT_USE_GRAPH=false`; útil auditoría ingest antiguo vs nuevo.

### Extensión y operadores Postgres

- **`pg_trgm`**: uso en `similarity()` para resolver aliases y FAQs por trigram antes de fusión por embedding.

### Migración

Implementada conceptualmente como **004 (`knowledge_restructure`)**. El README del repo documenta orden de aplicación de migraciones contra Railway.

---

## Pipeline ETL: Docling como puente PDF → texto estructurable

### Rol de Docling

- **Biblioteca oficial** integrada como extra pesado (`docling`) en **`services/backoffice-api`**; envuelta en **`PdfToMarkdownConverter`** (`docling_converter.py`) con cliente singleton para no reinstanciar el motor en cada request.
- Produce **Markdown** suficientemente estable como entrada de `StructuredMarkdownChunker`; el backoffice permite **preview de markdown post-conversión** (requisito de negocio: “no guardar bucket de PDF sí o sí”, pero sí inspeccionar transcripción).

### Robustez Docker / Railway

Commits recientes corrigen ejecución de Docling dentro de contenedor (dependencias/imagen) para que ingest en despliegue no falle por entorno diferente al local.

### `DocumentIngestService` (dual output)

Pipeline documentado encabezando `services/backoffice-api/src/app/services/etl_pipeline.py`:

1. Convierte PDF → Markdown (Docling o mock en CI).  
2. **Chunker legacy (`MarkdownChunker`)** sigue poblando **`document_chunks`** para compatibilidad y flag-off.  
3. **Chunker estructural (`StructuredMarkdownChunker`)** segmenta primero por **patrones conocidos Biomont** (numeración ficha/bitácora/bullets de balotario), guarda **`document_sections`**, genera **`knowledge_chunks`** con metadatos.  
4. Si `kind=balotario`, corre **FAQ extractor LLM único por documento** → **`faq_entries`**; errores marcados en `documents.classification` sin frenar ingest completo (`faq_extraction_failed`).

Parámetros de tamaño/overlap configurables desde `biomont_common.settings` (`knowledge_chunk_tokens`, overlap).

### Calibración con regex locales

Directorio **`docs/etl-regex-calibration/`** versiona:

- Guía **`README.md`** (estructuras `samples/etl-regex-calibration/{bitacora,ficha_tecnica,faq}/` locales ignoradas en Git).  
- **`ANALISIS_PATRONES_SECCIONES.md`** con patrones de encabezado esperados por familia de layout.

Commits agregaron **`.gitignore` de samples** + documentación explícita: el equipo calibra sobre PDFs/Markdown reales fuera del repositorio.

### Herramientas operativas

- Script **`bootstrap_products.py`**: alta idempotente de productos desde nombres de documentos y aliases heurísticos.  
- Endpoint admin **`POST /api/admin/documents/{id}/reingest`** (rol admin): borra chunks/secciones viejos y re-ejecuta ETL nuevo (transacciones / estados documentados en spec).

### Tests sin dependencias pesadas CI

Suite `test_etl_pipeline.py`: mocks para Docling y embeddings garantizando política `.cursor/rules/testing-policy-python.mdc`.

---

## Diseño del pipeline de búsqueda y generación de respuestas

### Principio conductor

Responder en WhatsApp/playground mediante **clasificación**, **resolver determinístico**, **filtros pre-retrieval** y sólo después **fusión embedding+BM25** (opcional cortocircuito FAQ), siempre dentro de país permitido RTC y con **abstención** si falta soporte («no inventar» policy del agente preservada del diseño inicial).

### Grafo LangGraph (nodos mínimos)

Flujo alto nivel (diagrama textual de spec 003):

```
IntentClassifier → ProductResolver ──ambiguous──► repregunta (low_confidence)
                        │
                        ▼
                  MetaFilter
                        │
               route por intent / señales
                   ┌────┴────┐
              FAQRetriever   HybridRetriever
                   └────┬────┘
                         ▼
                    Answerer (LLM estructurado + citaciones)
                         ▼
                    StateUpdater (persistencia conversation_state + agent_decisions)
```

| Nodo | Función práctica para la slide |
| ---- | -------------------------------- |
| `IntentClassifier` | Taxonomía de intenciones (dosis vs FAQ vs seguridad …) con modelo barato (`gpt-4o-mini`), salida schema JSON cacheable. |
| `ProductResolver` | Match exacto + trigram contra aliases; umbrales + margen top1-top2 ⇒ **ambiguous** ⇒ repregunta (evita errores típicamente peligrosos). Hereda producto anterior si usuario no renombra. |
| `MetaFilter` | Arma filtros declarativos: `product_id`, `kind` heurístico según intent, lista de países permitidos. |
| `FAQRetriever` | Búsqueda directa contra `faq_entries`; si score fusionado ≥ umbral ⇒ respuesta canonica rápido. |
| `HybridRetriever` | SQL combinando similitud coseno sobre `embedding` + `ts_rank_cd` sobre `tsv`; **normalización min-max** dentro conjunto candidato top-N antes de **`vector_weight * vec_norm + bm25_weight * bm25_norm`** (defaults 0.7 / 0.3 parametrizables). |
| `Answerer` | Compone prompt con fragmentos recuperados y genera **`RagAnswer` estructurado** (citaciones preservadas como en baseline LCEL). |
| `StateUpdater` | UPSERT estado conversación + registra **`graph_trace`**. |

Nodo **`Calculator`** declarado pero **sin implementación activa**: preparación para motor futuro de dosis.

### Fallback y banderas operativas

| Variable ejemplo | Rol |
| ---------------- | --- |
| `AGENT_USE_GRAPH` | Si `false`, agente ejecuta cadena LangChain/`document_chunks` antigua (rollback operativo rápido). |
| Pesos retrieval (`RAG_VECTOR_WEIGHT`, `RAG_BM25_WEIGHT`, `RAG_TOP_K`, …) | Afinación sin redesplegar lógica. |
| Umbrales FAQ / producto (`FAQ_DIRECT_THRESHOLD`, `PRODUCT_RESOLVER_THRESHOLD`, margen, …) | Calibración riesgo vs cobertura. |

### Observabilidad agregada

- Logs **`node_started/completed`** con latencias por nodo (`structlog`).
- Persistencia **`graph_trace`** permite reconstruir recorrido incluso cuando logs rotan.

### Dataset de evaluación (golden set)

Spec contempla **`services/agent/tests/eval/`** con preguntas curadas incluyendo regresiones obligatorias (Proteggo M vs gestación vs 3M, herencia estado, lexical vs semantic queries). Métricas: precisión resolver, intents, recall@5 hybrid vs sólo-vector, ratios FAQ direct-hit; baseline JSON versionado para CI.

---

## Nuevas secciones del backoffice web (detalle lista para demos)

Ubicaciones reales (`services/backoffice-web/app/(dashboard)/`):

| Ruta conceptual | Implementación típica | Valor usuario |
| --------------- | --------------------- | ------------- |
| **Productos** | `/products`, `/products/[id]` | CRUD productos, gestión aliases, cuenta documentos relacionados sin depender sólo SQL/. |
| **Decisiones del agente** | `/agent-decisions`, `/agent-decisions/[id]` | Auditoría soporte/clínico: decisión (`answered`, `no_match`, …), `retrieved`, `graph_trace`. |
| **Documento mejorado** | `/documents/[id]` con tabs | Tabs: Markdown, Secciones, Chunks retrieval, FAQ cuando aplique, Chunks legacy (comparativo). Paginación server-side donde la spec obliga lazy load de chunks grandes. |

### APIs backend asociadas (spec 004)

Patrón: REST bajo mismo auth JWT/session que el resto del BO:

- `/products`, `/products/{id}` + CRUD aliases.  
- `/agent-decisions`, `/agent-decisions/{id}` con filtros (decisión, fechas, teléfonos normalizados, conversación UUID).  
- `/documents/{id}/sections`, `.../knowledge-chunks`, `.../document-chunks` (legacy opcional), `.../faq-entries`.

Persistencia encapsulada en repositorios (regla `.cursor/rules/dependency-constraints.mdc`).

### Roles (RBAC) — mensaje ejecutivo rápido

| Rol | Puede hacer |
| --- | ----------- |
| `viewer` | Leer todo lo operativo nuevo. |
| `scientist` | Mutar catálogo y aliases; cargar documentos (según despliegue). |
| `admin` | Borrar productos (con chequeo dependencias alias/docs) + políticas administrativas. |

### Feedback visual y estados asíncronos (spec 005)

Cubrimiento dirigido:

- Pending en submits (prevenir double POST).  
- Toasts/snackbars de éxito **una vez** por acción.  
- Errores con `detail` FastAPI cuando existan.  
- Subida PDF con indicadores explícitos (acción larga).  
- Mínimos accesibles (`aria-busy` donde aplica).

Esto cerró hueco donde operadores sólo inferían resultado por cambio tardío de tabla.

---

## Contexto anterior relevante mencionado en presentación

### Conversaciones espejo + playground (spec 002)

Dos columnas estilo WhatsApp Web (lectura sincera de `messages`); playground en modal/tablet ejecuta mismo orquestador con flag `skip_whatsapp_send` ⇒ **sin ping doble al cliente**. Crítico demostrar coherencia de transcript operaciones internas ↔ canal real.

### Infra CI / Railway

Commits de **`watch paths` por servicio** reducen redespliegues cruzados en monorepo. Ajustes en **PORT de Railway fallback local** Docker Compose y fixes de sesión API↔front en contenedores.

---

## Comparativa “mensaje tipo CEO” vs “mensaje CTO”

### CEO / negocio

- Menor riesgo de **respuesta equivocada de producto** gracias a alias + thresholds + estado conversacional.
- Auditoría navegable ⇒ soporte rápido y confianza científica ante disputas sobre “qué dijo el bot”.
- Carga PDF → pipeline auditable hasta fragmento granular y FAQ.

### CTO / ingeniería

- Schema evolutivo con dual-write ETL sin big-bang downtime (feature flag grafo).
- Índices adecuados: HNSW vector, GIN `tsvector`, trigram alias/FAQ.
- Tests desacoplados de docling/red LLM externos (mocks coherentes política proyecto).

---

## Sugerencias de estructura de presentación derivada automáticamente

| Slide # | Título sugerido |
| ------- | ---------------- |
| 1 | Visión Biomont: WhatsApp + corpus validado |
| 2 | Problema antes: todo mezclado vectorialmente |
| 3 | Nueva entidad conocimiento orientada PDF |
| 4 | ETL Docling + chunker estructural + FAQ extractor |
| 5 | Modelo Postgres (diagrama textual arriba) |
| 6 | Grafo agente LangGraph paso a paso |
| 7 | Retrieval híbrido: por qué suma lexicalidad |
| 8 | Pantallas nuevas BO: productos, decisiones, documento multimodal técnico |
| 9 | UX asíncrona operadores |
| 10 | Operación: bootstrap productos / reingest / flags rollback |
| 11 | QA & evaluaciones (golden set) |
| 12 | Próximo hito plausible: Calculator / tablas dosing estructural (ADR Fase 2 en spec 003) |

---

## Lista de chequeo “demo en vivo” (para guion corto IA)

1. Mostrar alta producto + alias “coloquiales”.  
2. Subir tres familias de PDF (idealmente bitácora, ficha técnica, balotario) con `kind` correcto.  
3. Validar ingest → revisar pestañas Secciones/Chunks en documento balotario (FAQ aparece?).  
4. Enviar pregunta en playground que fuerce **`ambiguous_product`** (sin alias claro).  
5. Reenviar con alias exacto ⇒ ver recuperación plausible + **decisión `answered`** y `retrieved` no vacíos.  
6. Abrir detalle **`agent-decisions/[id]`** y expandir `graph_trace`.
