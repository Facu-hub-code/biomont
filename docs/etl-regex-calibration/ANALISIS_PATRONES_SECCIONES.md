
# Análisis de patrones de título (PDF → texto extraído)

> **Ubicación de los PDF:** carpeta local `samples/etl-regex-calibration/` (no versionada).

**Método:** extracción con `pypdf` sobre las primeras páginas de cada archivo en esta carpeta. El pipeline real usa Docling → **markdown con `##`** en muchos casos; por eso al final hay recomendaciones que cubren **tanto texto plano PDF como markdown**.

**Implementación actual:** `StructuredMarkdownChunker` en  
`services/common/src/biomont_common/integrations/text_splitter.py`.

---

## 1. Bitácoras: dos familias de “macro-sección”

### Familia A — `N°` (grado Unicode)

Ejemplos reales del corpus:

- `1° Generalidades del principio activo`
- `2° Protocolos de uso`

**Archivos:** `KUAGULA_Bitacora.pdf`, `SERENTIS_Bitacora.pdf`, `OPRURIX_Bitacora.pdf`, `PROTEGGO 3M y M_Bitacora.pdf`, `MARVO 20_Bitácora.pdf` (primer bloque).

**Regex actual `_BITACORA_MACRO_RE`:** coincide con esta familia cuando la línea **no** lleva prefijo `##`.

### Familia B — `N.` (punto, sin segundo número)

Ejemplos reales:

- `1. Generalidades del principio activo`
- `2. Protocolos de uso`
- `3. Formulaciones de laboratorios externos`

**Archivos:** `BITACORA - AUMENTHA ATP NF.pdf`, `BITACORA - TULABIOT .pdf`, `BITACORA - GIGANTOL ADE Y SEMENTAL.pdf`, `BITACORA - HEPATIN.pdf`, etc.

**Problema:** la regex `_BITACORA_MACRO_RE` exige **`N°`**, no **`N.`** → en Familia B la macro **no matchea**. El segmentador depende de que existan subtítulos `1.1`, `2.1`, etc.; el encabezado “1.” queda fuera del modelo de macro o mezcla con el contenido según orden de líneas.

**Conclusión:** hace falta **tratar `N.` titulo como macro alternativa**, con cuidado de no confundir con párrafos numerados dentro del texto (ver TILOZONA).

### Subsecciones `N.M`

Patrón estable en casi todas las bitácoras:

- `1.1 Naturaleza farmacológica...`
- `2.3 Porcinos – Brote respiratorio...`

**Regex actual `_BITACORA_SUB_RE`:** encaja bien en la mayoría de los casos.

### Nivel `N.M.P` (tres niveles)

Ejemplos: `1.2.1 Eje purinérgico...`, `1.4.3. Vitamina B12...` (variaciones con punto final).

**Regex actual:** solo **`N.M`** de dos fragmentos → esas líneas **no** abren sección dedicada en el modelo actual.

### Caso especial: TILOZONA

Aparecen líneas tipo **`1.`** / **`2.`** que son párrafos de lista dentro del contenido (“1. Control etiológico…”). Cualquier macro **`N.`** laxa debe acotarse (p. ej. longitud máxima de título, mayúscula inicial exclusiva para bitácora, o lista de exclusiones como “solo si va seguido de subtítulo `1.1` en las próximas líneas”, etc.).

---

## 2. Fichas técnicas: patrón muy estable

Ejemplos: `1. CLASIFICACIÓN`, `9. DOSIFICACIÓN`, `10. PERIODO DE RETIRO` (español e inglés: `3. QUALITATIVE...`).

**Regex `_FT_SECTION_RE`:** **funciona bien** cuando el PDF entrega líneas limpias con:

- dígito(s) + `.` + espacio +
- **título en mayúsculas** (ASCII y con acentos en el set permitido).

**Riesgos:** caracteres OCR raros, o conversión Markdown que antepon **`##`** a la línea — hay que normalizar igual que para bitácora antes del split.

---

## 3. Balotarios / FAQ: dos formatos predominantes

### Formato A — Viñeta + pregunta

- `• ¿Se puede utilizar Kuagula en gestación…?`

**Regex `_BALOTARIO_Q_RE`:** coincide (presente en Kuagula, Marvo 20, Oprurix, Proteggo, parte de Serentis).

### Formato B — Número + pregunta (sin viñeta)

- `1. ¿Por qué se recomienda aplicar…?`
- `2. ¿El ATP presente…?`

**Archivos:** `BALOTARIO - AUMENTHA ATP NF.pdf`, `BALOTARIO - TILOZONA.pdf`, `BALOTARIO - TULABIOT.pdf`, `BALOTARIO HEPATIN.pdf`, etc.

**Problema:** **no matchean** `_BALOTARIO_Q_RE` (exige líder `•`).

### Formato C — inconsistencias espaciales / numeración

- `2 ¿Se puede usar…` (sin punto tras el número)

**Archivo:** `Balotario - GIGANTOL ADE Y SEMENTAL.pdf`

Requiere patrón adicional laxo opcional (`N.` o `N` opcional + `¿`).

---

## 4. Recomendaciones para el siguiente cambio en código

1. **Normalización previa al split (crítico con Docling):**  
   En líneas tipo `## 1° Generalidades…` o `## 2. PROTOCOLOS` — **retirar** `#{1,6}\s+` y reintentar los matchers de macro/sub/ficha/FAQ sobre el resto.

2. **Bitácora — macro unificada:**  
   Admitir equivalencia **`N°` ≈ `N.`** cuando `N` tiene 1–2 dígitos y el resto parece título (línea corta, sin punto final masivo). Añadir heurísticas anti-falso positivo usando TILOZONA como caso de tensión.

3. **FAQ — segunda regex:**  
   `^\s*(?P<num>\d{1,2})\.\s*(?P<question>¿.+?\?)\s*$`  
   y opcionalmente número sin punto cuando se valide contra corpus.

4. **Subsección `N.M.P`:**  
   Decidir si se modela como sección hijo de `N.M` o se deja dentro del `raw_text` del padre; implica cambio de modelo de jerarquía, no solo regex.

5. **Validación:**  
   Tras cambiar regex, correr ingesta de **una bitácora Familia A**, **una Familia B**, **una ficha**, **un balotario A y otro B** y comprobar `etl_no_sections_detected`.

---

## 5. Inventario rápido (archivos revisados)

| Carpeta       | Cantidad útil | Observación breve                                      |
|---------------|---------------|--------------------------------------------------------|
| `bitacora/`   | 11            | Mix `1°` vs `1.`; subs `N.M`; TILOZONA con ruido `1.`  |
| `ficha_tecnica/` | 9          | Encaje fuerte con `N. MAYÚSCULAS`                      |
| `faq/`        | 12            | Mitad bullet `• ¿`, mitad numerada `N. ¿`               |

Este documento no sustituye pruebas con **markdown real de Docling**; conviene capturar 1 página de cada familia después de conversión y fijar goldens en tests unitarios sobre `StructuredMarkdownChunker`.

## 6. Cambios aplicados en codigo (`StructuredMarkdownChunker`)

- Prefijo Markdown `#{1–6}` normalizado antes de matchear (Docling).
- Macro bitácora `N°`/`Nº` y macro `N.` con `_accept_bitacora_macro_dot` (pistas desde corpus + exclusión por ` mediante ` + prefixes tipo MARVO/`otros microorganismos`).
- Subseccion `N.M` con segundo punto opcional (`1.2. Interacciones`), estilo SERENTIS PDF.
- Balotarios: `N. ¿...?`, `N ¿...?`, además del bullet `• ¿...?`.
