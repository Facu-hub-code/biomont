# Manual de usuario Backoffice Biomont

Este manual detalla el uso operativo del backoffice para:

- Gestion de documentos PDF y su ingestion.
- Catalogo de productos y aliases.
- Auditoria de decisiones del agente.
- Revision de secciones/chunks/FAQ por documento.

Referencia tecnica: [Spec 004](./specs/004-backoffice-products-documents-and-agent-decisions.md).

## 1) Roles y permisos

- `viewer`: lectura de documentos, productos y decisiones.
- `scientist`: lectura + alta/edicion de productos y aliases, carga de documentos.
- `admin`: todo lo anterior + eliminacion de productos.

Si una accion falla por permisos, el sistema devuelve `403`.

## 2) Carga de PDFs: flujo recomendado

Ruta: `Documentos`.

### 2.1 Preparacion previa

Antes de subir el PDF, definir:

1. Tipo documental (`kind`):
   - `ficha_tecnica`: informacion formal de producto.
   - `bitacora`: material de campo/uso frecuente.
   - `balotario`: formato pregunta-respuesta (habilita FAQ).
2. Producto asociado:
   - Preferido: seleccionar `Producto (catalogo)` para usar `product_id`.
   - Alternativo: completar `Producto` (texto libre `product_name`) cuando aun no exista en catalogo.

### 2.2 Paso a paso de carga

1. Ir a `Documentos`.
2. Completar:
   - `Archivo PDF`.
   - `Titulo`.
   - `Producto (catalogo)` si existe.
   - `Producto` (texto) solo si no se eligio producto de catalogo.
   - `Pais (iso2)` o vacio para global.
   - `Idioma` (por defecto `es`).
   - `Tipo` (`ficha_tecnica`, `bitacora`, `balotario`).
3. Presionar `Procesar y validar`.
4. Verificar estado y abrir detalle.

### 2.3 Buenas practicas de ingestion

- Cargar PDFs limpios, con texto seleccionable y sin escaneos borrosos.
- Mantener un criterio unico de nombres de producto para minimizar aliases redundantes.
- Para `balotario`, validar que las FAQ extraidas tengan preguntas claras y respuestas completas.
- Evitar cargar el mismo PDF repetidas veces (el sistema valida hash cuando corresponde).
- Usar pais (`country_iso`) cuando el contenido sea regulatorio/local.

## 3) Gestion de productos y aliases

Ruta: `Productos`.

### 3.1 Crear producto

1. Completar `Nombre`, `Marca`, `Pais ISO2` (opcional), `Tipo de duracion`, `Descripcion`.
2. Guardar.

Si existe conflicto de unicidad (nombre + pais), aparece error de conflicto (`409`).

### 3.2 Editar producto

1. Abrir `Ver detalle`.
2. Editar campos.
3. Guardar cambios.

### 3.3 Eliminar producto (solo admin)

1. Entrar al detalle.
2. Presionar `Eliminar producto`.
3. Confirmar segun el navegador/flujo.

Si hay referencias incompatibles, puede devolverse conflicto (`409`).

### 3.4 Gestion de aliases

En detalle de producto:

- Agregar alias con `Fuente` y `Confianza`.
- Editar alias en linea y guardar.
- Eliminar alias obsoletos.

Recomendaciones:

- Registrar variantes reales usadas por RTCs (abreviaciones, errores frecuentes, nombres comerciales).
- No duplicar aliases equivalentes (normalizados).

## 4) Auditoria de decisiones del agente

Rutas:

- `Decisiones del agente` (listado).
- `Decisiones del agente/{id}` (detalle).

### 4.1 Listado y filtros

Filtros soportados:

- `decision`: `answered`, `low_confidence`, `no_match`, `blocked`, `error`.
- `phone`: telefono (se normaliza por digitos).
- `conversation_id`: UUID de conversacion.

Uso sugerido:

1. Empezar por `decision=no_match` o `low_confidence`.
2. Refinar por telefono de RTC reportado.
3. Abrir detalle para confirmar razonamiento y retrieval.

### 4.2 Lectura de detalle

Campos clave:

- `reasoning`: explicacion textual de la decision.
- `retrieved`: chunks/documentos recuperados.
- `top_similarity`: similitud maxima reportada.
- `graph_trace`: pasos del grafo/nodos con payload.
- `message_content` y `previous_user_message`: contexto conversacional.

Checklist operativo:

1. Confirmar que el retrieval apunte al documento correcto.
2. Revisar si `top_similarity` es consistente con la decision.
3. Inspeccionar `graph_trace` para detectar nodos lentos o decisiones de fallback.
4. Si falta conocimiento, coordinar carga/reingesta del PDF correspondiente.

## 5) Revision de documento por pestañas

Ruta: `Documentos/{id}`.

Orden recomendado de revision:

1. `Markdown`: confirmar conversion base del PDF.
2. `Secciones`: validar estructura y jerarquia.
3. `Chunks (retrieval)`: revisar fragmentacion y metadatos.
4. `FAQ`: verificar calidad de pares pregunta-respuesta (si aplica).
5. `Legacy chunks`: comparar contra pipeline anterior.

### 5.1 Que revisar en Secciones

- Titulos esperados.
- Indices ordenados.
- Coherencia de paginas.
- Texto sin cortes severos.

### 5.2 Que revisar en Chunks (retrieval)

- Cobertura del contenido relevante.
- `contains_dose` / `contains_table` cuando corresponda.
- `token_count` razonable.
- Fragmentos no vacios ni truncados en exceso.

### 5.3 Caso sin chunks nuevos

Si la pestaña retrieval esta vacia y hay `legacy chunks`, el documento probablemente no fue reingestado bajo el esquema nuevo.

## 6) Ejemplos de consultas de chat post-ingestion

Tras ingerir correctamente, ejemplos de consultas esperadas por WhatsApp/contexto agente:

- "¿Cada cuanto debo aplicar [producto] en bovinos?"
- "¿Que dosis recomienda [producto] para terneros?"
- "Comparame [producto A] vs [producto B] para control de parasitos."
- "¿Este producto aplica para Peru?"
- "Mostrame contraindicaciones del producto [X]."

Si las respuestas derivan en `no_match` o `low_confidence`, revisar:

1. Producto y aliases cargados.
2. Calidad de chunks del documento.
3. Cobertura del contenido faltante.

## 7) Procedimiento operativo sugerido (end-to-end)

1. Crear/validar producto y aliases.
2. Cargar PDF con `kind` correcto.
3. Revisar documento por tabs.
4. Probar 3-5 preguntas representativas en canal agente.
5. Auditar decisiones en backoffice.
6. Ajustar aliases o reingestar si hay brechas.

## 8) Errores frecuentes y resolucion

- `401`: sesion vencida/no autenticada -> volver a iniciar sesion.
- `403`: rol sin permisos -> escalar a perfil habilitado.
- `404`: recurso inexistente -> validar ID/URL.
- `409`: conflicto de unicidad o referencia -> corregir dato duplicado o dependencia.

## 9) Trazabilidad y referencia tecnica

Toda la funcionalidad de este manual sigue la definicion de:

- [Spec 004](./specs/004-backoffice-products-documents-and-agent-decisions.md)

Para detalles de arquitectura o alcance, usar esa spec como fuente canonical.
