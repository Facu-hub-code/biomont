# Manual de usuario extendido — Backoffice Biomont (corpus para asistentes / IA)

**Version del documento:** 1.0  
**Audiencia:** operadores internos, soporte, equipo cientifico; y **modelos de lenguaje** que necesitan contexto operativo estable.  
**Fuentes normativas del repositorio:** [Spec 003](./specs/003-langgraph-hybrid-rag-and-knowledge-restructure.md), [Spec 004](./specs/004-backoffice-products-documents-and-agent-decisions.md).  
**Manual resumido (lectura humana rapida):** [manual-usuario-backoffice.md](./manual-usuario-backoffice.md).

---

## Como usar este documento para alimentar una IA

Este archivo esta redactado para que un sistema de IA pueda:

1. **Responder procedimientos** paso a paso sin inventar pantallas inexistentes (se usan rutas conceptuales: `Documentos`, `Productos`, `Decisiones del agente`).
2. **Mantener terminos estables** (glosario): mismo nombre para `kind`, roles, tipos de decision.
3. **Distinguir hechos de producto** de **supuestos**: donde hay variacion por despliegue (URLs, credenciales), se indica explicitamente.
4. **Escalar troubleshooting** segun codigos HTTP y tipo de decision del agente.

**Instrucciones sugeridas al copiar este texto a un system prompt de un bot interno:**

- Cita siempre la **fuente del dato** (documento validado, FAQ, o "no consta en corpus") alineado con las reglas del `system_prompt` activo en Biomont.
- No inventes URLs de API; indica "usar el backoffice autenticado" salvo que el operador provea `base URL`.
- Ante sintomas de **datos vacios**, prioriza checklist: producto/aliases -> documento ingestado -> pestañas de verificacion -> decisiones `no_match` / `low_confidence`.

---

## 1. Vision general del sistema

Biomont conecta:

1. **Canales de conversacion** (p. ej. WhatsApp hacia usuarios RTC registrados) con un **agente** que responde usando **recuperacion de conocimiento** (RAG) sobre documentos validados.
2. Un **backoffice web** donde el equipo:
   - carga y valida **PDFs**;
   - gestiona el **catalogo de productos** y **aliases**;
   - **audita** cada decision persistida (`agent_decisions`) vinculada a mensajes y conversaciones.
3. Una **base PostgreSQL** (con **pgvector**) donde viven textos, embeddings y metadatos de fragmentos.

**Flujo logico de una pregunta de usuario:**

`Mensaje usuario` → `clasificacion / grafo del agente` → `retrieval` (hibrido vectorial + texto) sobre `knowledge_chunks` (y otros canales como FAQ en balotario) → `generacion de respuesta` con politica de abstencion si no hay match → persistencia en `messages` + `agent_decisions` (trazas, `retrieved`, `graph_trace` opcional).

---

## 2. Glosario canonico

| Termino | Significado |
| --------| ----------- |
| **RTC** | Usuario final habilitado (`rtc_users`), identificado tipicamente por telefono E.164. |
| **Conversacion** | Hilo `conversations` ligado a un `rtc_user_id`; contiene `messages`. |
| **Documento** | Fila en `documents`: PDF ingerido, con `title`, `kind`, `status`, texto en `markdown`, posible `product_id` / `product_name`, `country_iso`. |
| **kind** (tipo documental) | Enum de dominio: `ficha_tecnica`, `bitacora`, `balotario`. Afecta chunking y pipelines (p. ej. FAQ en balotario). |
| **Producto** | Entidad `products` (nombre, marca, pais opcional, etc.). |
| **Alias** | Variante textual en `product_aliases` que permite matchear lenguaje natural; tiene `normalized_alias` unico por producto. |
| **Seccion** | `document_sections`: bloque estructural del documento (indice, titulo, jerarquia). |
| **Chunk (retrieval)** | `knowledge_chunks`: fragmento con `content`, embedding, metadatos (`contains_dose`, `contains_table`, `kind`, etc.). Es la pieza principal del retrieval moderno. |
| **Chunk legacy** | `document_chunks`: pipeline anterior; puede coexistir durante migracion; sirve para comparar. |
| **FAQ** | `faq_entries`: pares pregunta-respuesta (tipicamente desde balotario), con su propio embedding. |
| **Decision del agente** | Fila `agent_decisions`: clasifica el resultado del turno (`answered`, `low_confidence`, `no_match`, `blocked`, `error`) con razonamiento y contexto recuperado. |
| **graph_trace** | JSON con pasos del grafo (nodos, tiempos, payloads); aparece cuando el camino LangGraph registro traza. |
| **Retrieved** | Lista estructurada de referencias recuperadas (documentos/chunks/similitud); inspeccionable en el BO. |

---

## 3. Roles del backoffice (RBAC)

Roles en `bo_role`: `viewer`, `scientist`, `admin`.

| Accion | viewer | scientist | admin |
| ------ | :----: | :-------: | :---: |
| Ver documentos, pestañas tecnicas, productos, decisiones | si | si | si |
| Crear / editar productos y aliases | no | si | si |
| Cargar / gestionar documentos (segun politica desplegada) | no | si | si |
| Eliminar producto | no | no | si |

**Notas para IA:**

- `403 Forbidden`: el usuario autenticado no tiene rol suficiente; no es un bug de red.
- `401 Unauthorized`: sesion invalida o ausente; reautenticar.

---

## 4. Modelo de datos conceptual (alto nivel)

Sin credenciales ni host; solo para razonar dependencias:

- `countries` — catalogo ISO-2; no se borra en resets operativos tipicos.
- `bo_users` — operadores del backoffice.
- `rtc_users` / `rtc_user_countries` — quien puede chatear desde WhatsApp y mercados.
- `products` ← `product_aliases`
- `documents` — opcionalmente `product_id`; texto `product_name` historico/libre.
- `document_sections` — jerarquizacion por `document_id`.
- `knowledge_chunks` — fragmentos + embeddings + BM25 (`tsv`).
- `document_chunks` — legacy.
- `faq_entries` — vinculadas a `document_id` (y opcionalmente `product_id`).
- `conversations` ← `messages`; `conversation_state` memo de contexto.
- `agent_decisions` — referencia `message_id`; traza decision + `retrieved` + `graph_trace`.
- `bo_audit_log` — mutaciones sensibles del BO (productos, aliases, documentos segun implementacion).

**Orden mental ante “no encuentra el producto”:** alias y nombre de producto coherentes → documento con `product_id` o metadata correcta → chunks presentes → similitud suficiente en retrieval.

---

## 5. Procedimiento completo: de cero a respuesta verificable

### 5.1 Precondiciones

- Usuario BO con rol adecuado (`scientist` o superior para cargas).
- Base accesible; **no** se documentan aqui credenciales ni `DATABASE_URL`.
- Para pruebas de chat: RTC existente o alta previa de `rtc_users` (fuera del alcance de este manual si el proceso es manual/SQL).

### 5.2 Paso A — Catalogo de producto

1. Abrir **Productos**.
2. Crear producto con **nombre** y **marca** alineados al material oficial.
3. Indicar **pais** (`country_iso`) cuando la politica del equipo exija segmentacion (regulatoria o comercial). Vacio puede interpretarse como “global” segun reglas de unicidad en BD.
4. Anadir **aliases** que cubran:
   - nombre comercial abreviado;
   - errores ortograficos frecuentes;
   - como habla el cliente en WhatsApp (“el de 3 meses”, marca + dosis).
5. Evitar duplicados: el sistema **normaliza** texto de alias al validar unicidad.

**Criterio de calidad:** un operador humano debe poder reconocer en menos de 10 segundos que el alias corresponde al producto correcto.

### 5.3 Paso B — Subida del PDF (Documentos)

1. Ir a **Documentos**.
2. Adjuntar **PDF** (texto seleccionable preferible; OCR de baja calidad degrada el RAG).
3. Completar **Titulo** descriptivo (aparece en citas y listados).
4. Elegir **Tipo (`kind`)** correcto:
   - **ficha_tecnica**: datos tecnicos formales.
   - **bitacora**: soporte de campo / narrativa operativa.
   - **balotario**: si el PDF es pregunta-respuesta; habilita extraccion/indexacion de FAQ.
5. Asociacion de producto (mejor esfuerzo):
   - **Opcion preferida:** seleccionar del **catalogo** (`product_id`).
   - **Opcion alternativa:** texto libre `product_name` si aun no hay producto; en backend puede intentarse **match automatico** contra aliases solo si la similitud supera umbral alto (p. ej. 0.95 en implementacion actual). Si no matchea, el documento puede quedar **sin** `product_id`.
6. **Pais** e **idioma** cuando apliquen filtros regulatorios o de idioma del modelo de embeddings/chunking.
7. Enviar a **procesar / validar** (terminologia exacta del boton puede variar en UI).

**Errores frecuentes subjetivos (no son codigos HTTP):**

- Producto equivocado en catalogo → retrieval mezclado o irrelevante.
- `kind` incorrecto → estructura de secciones y FAQ suboptimas.

### 5.4 Paso C — Verificacion tecnica en el detalle del documento

Abrir **Documentos / {id}** y revisar en orden:

1. **Markdown / texto:** conversión PDF razonable (sin muro de texto ilegible).
2. **Secciones:** jerarquia y titulos esperados; detectar cortes anomalos.
3. **Chunks (retrieval):** cobertura del contenido critico; revisar banderas `contains_dose` / `contains_table` cuando importe la pregunta.
4. **FAQ** (si aplica): pares completos y sin truncamiento absurdo.
5. **Legacy:** comparacion solo si hubo migracion desde pipeline viejo.

Si **Chunks (retrieval)** esta vacio pero hay legacy, el documento **no fue reingestado** bajo el esquema nuevo: se requiere **reingesta** (ver seccion 8).

### 5.5 Paso D — Prueba conversacional (canal agente)

Disparar desde WhatsApp (o canal conectado) preguntas **cerradas** que el PDF responde textualmente, luego **abiertas** que requieren sintesis.

#### Banco de ejemplos de prompts (adaptar nombre de producto)

**Dosis y uso**

- "¿Cual es la dosis de {producto} en bovinos adultos?"
- "¿Cada cuantos dias se reaplica {producto} en ganado?"
- "¿Hay diferencia de dosis entre terneros y vacas en {producto}?"

**Seguridad y restricciones**

- "¿Cuales son las contraindicaciones de {producto}?"
- "¿Se puede usar {producto} en animales en lactancia?"

**Comparacion y eleccion**

- "Compara {producto A} y {producto B} para parasitos gastrointestinales en bovinos."
- "Si tengo {sintoma X}, ¿conviene {producto A} o {producto B}?"

**Alcance geografico / regulatorio**

- "¿Este documento aplica a {pais}?"

**FAQ / balotario**

- Preguntas literales tomadas del texto del balotario (deben matchear fuerte).

**Para IA:** usar siempre el **nombre/alias** que el usuario final usaria; si falla, repetir con alias alternativo registrado.

### 5.6 Paso E — Auditoria en "Decisiones del agente"

1. Abrir **Decisiones del agente**.
2. Filtrar por `decision` problematica primero (`no_match`, `low_confidence`, luego `error`).
3. Opcional: filtrar por **telefono** del RTC o **UUID de conversacion** si el soporte lo aporta.
4. Abrir **detalle**:
   - leer `reasoning`;
   - inspeccionar `retrieved`: ¿los `document_id`/`chunk_id` esperados?;
   - anotar `top_similarity`;
   - revisar `graph_trace` si el fallo es de **routing** (nodo equivocado) vs **retrieval** (sin texto util).

**Matriz de interpretacion (orientativa, no exhaustiva):**

| Sintoma en BO | Hipotesis tipica | Accion |
| --------------- | ---------------- | ------ |
| `no_match` + retrieved vacio | Corpus sin texto relevante o embedding lejano | Revisar chunks; ampliar aliases; subir doc faltante |
| `no_match` + retrieved con doc equivocado | Producto/alias mal asociado | Corregir `product_id` / aliases; reingestar si hace falta |
| `low_confidence` + similitud media | Prompt o umbral; fragmentos parciales | Revisar chunking; reformular FAQ |
| `error` | Infra/modelo/formato | Revisar logs de servicio agente (fuera de este manual) |
| `graph_trace` lento en un nodo | Optimizacion/costo; no siempre calidad de dato | Marcar para ingenieria |

---

## 6. Ingesta automatica de producto por nombre (cuando no hay `product_id`)

**Comportamiento conceptual** (segun implementacion ETL): si solo se envia **texto** de producto, el sistema busca candidatos contra aliases; si el mejor candidato alcanza **alta similitud**, se asigna `product_id`. Si no, el documento puede guardarse **sin** enlace fuerte al catalogo.

**Implicaciones para operadores e IA:**

- No asumir que "siempre" habra `product_id` solo por escribir un nombre parecido.
- La fuente de verdad para pruebas repetibles es **seleccion explicita en catalogo**.

---

## 7. Duplicados de documento (hash de contenido)

El pipeline calcula hash del binario PDF (`content_sha256`). Si se sube el **mismo archivo** nuevamente, puede detectarse duplicidad y **no repetir** trabajo (mensaje/logica segun servicio).

**Para IA:** si el operador "no ve cambios" tras re-subir el mismo PDF, puede ser comportamiento esperado; para forzar reprocesamiento usar **reingesta** sobre el documento existente (seccion 8), no duplicar uploads como estrategia principal.

---

## 8. Reingesta

La reingesta vuelve a ejecutar el pipeline sobre un **documento ya existente** (endpoint administrativo de API; uso tipico desde herramientas internas o evolucion futura de UI).

**Para IA:** describelo como "reprocesar markdown + chunks + embeddings" sin editar texto en SQL crudo; la spec explicitamente **no** habilita editar `knowledge_chunks` manualmente en BD sin proceso de invalidacion de embeddings.

---

## 9. Reset de entorno de pruebas (limpieza operativa)

Existe script SQL versionado y un wrapper shell en el repositorio:

- `scripts/reset_operational_data.sql`
- `scripts/reset_operational_data.sh`

Vacian datos operativos (conversaciones, mensajes, decisiones, documentos, vectores, productos, auditoria BO segun script) **preservando** p. ej. `countries`, `bo_users`, `rtc_users`, `system_prompts`.

**Advertencia:** destructivo; solo entornos controlados con backup/PITR.

**Para IA:** nunca sugerir reset en produccion sin confirmacion humana explicita y politica de backup.

---

## 10. Codigos HTTP y significado en el BO

| Codigo | Significado practico |
| ------ | --------------------- |
| 200 / 201 | Operacion exitosa. |
| 400 | Payload invalido (enum, campo faltante). |
| 401 | No autenticado. |
| 403 | Autenticado pero rol insuficiente. |
| 404 | Recurso no existe. |
| 409 | Conflicto de negocio (unicidad producto/alias, dependencias). |
| 415 | Tipo de archivo no aceptado (p. ej. no PDF). |

---

## 11. Enum `agent_decision_kind` (valores persistidos)

Valores tipicos (segun migraciones): `answered`, `low_confidence`, `no_match`, `blocked`, `error`.

**Descripciones operativas:**

- **answered:** el pipeline considero que hubo respuesta suficientemente fundada.
- **low_confidence:** hubo contexto pero insuficiente o ambiguo segun politica.
- **no_match:** no se encontro soporte adecuado en corpus/recuperacion.
- **blocked:** politicas de seguridad o de contenido impidieron responder (detalle en `reasoning` / trazas).
- **error:** fallo tecnico en cadena (modelo, formato, timeout, etc.).

**Para IA:** no contradecir el enum; si el operador describe un sintoma distinto, mapear al valor mas cercano y pedir **ID de decision** para auditoria.

---

## 12. Buenas practicas (resumen ejecutable)

1. **Catalogo antes que texto libre** cuando haya tiempo: `product_id` reduce ambiguedad.
2. **Aliases ricos** mejoran recall en lenguaje natural conversacional.
3. **Elegir `kind` correcto** antes de procesar; cambiarlo implica reingesta.
4. **Validar chunks** en el BO antes de masivas campañas de WhatsApp.
5. **Auditar** `no_match` y `low_confidence` de forma sistematica; son la cola de calidad del corpus.
6. **No inventar** contenido clinico: el agente esta acotado por documentos validados y prompts del sistema.

---

## 13. Limitaciones explicitas (v1 / fuera de alcance frecuente)

- El BO **no** es editor SQL de chunks: corregir conocimiento implica **nuevo PDF**, **reingesta**, o cambios gobernados por ingenieria de datos.
- Export masivo CSV de decisiones puede no existir en v1.
- Tiempo real (WebSocket) en listados: no requerido; puede ser polling/refresco manual.

---

## 14. Apendice A — Plantilla de "informe de incidente de calidad" (para humanos o IA)

1. **ID conversacion** o telefono E.164 del RTC.  
2. **ID decision** (si existe) y valor de `decision`.  
3. **Pregunta usuario** (texto literal).  
4. **Respuesta agente** (texto literal o captura).  
5. **Documentos esperados** (titulos) vs **documentos en `retrieved`**.  
6. **top_similarity** observado.  
7. **Accion propuesta:** alias / nuevo PDF / reingesta / escalamiento ingenieria.

---

## 15. Apendice B — Referencias cruzadas

- Arquitectura RAG y tablas: [Spec 003](./specs/003-langgraph-hybrid-rag-and-knowledge-restructure.md).  
- Alcance backoffice y criterios de aceptacion: [Spec 004](./specs/004-backoffice-products-documents-and-agent-decisions.md).  
- Manual corto operativo: [manual-usuario-backoffice.md](./manual-usuario-backoffice.md).

---

*Fin del manual extendido. Mantener alineado con las specs al cambiar comportamiento del producto.*
