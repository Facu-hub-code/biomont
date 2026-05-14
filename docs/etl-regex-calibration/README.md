# Calibración de regex ETL (bitácora / ficha técnica / FAQ)

Los PDFs de referencia para afinar `StructuredMarkdownChunker` viven en el repo solo de
forma **local**: carpeta **`samples/etl-regex-calibration/`** en la raíz del monorepo
(ignorada por Git; ver `.gitignore`).

**Documentación versionada aquí:**
[ANALISIS_PATRONES_SECCIONES.md](./ANALISIS_PATRONES_SECCIONES.md)

## Estructura (local, bajo `samples/etl-regex-calibration/`)

| Carpeta | `DocumentKind` en código | Ejemplos esperados |
|---------|--------------------------|--------------------|
| `bitacora/` | `bitacora` | Bitácoras clínicas / de campo |
| `ficha_tecnica/` | `ficha_tecnica` | Fichas regulatorias o monografías numeradas |
| `faq/` | `balotario` | Material tipo preguntas frecuentes (balotario) |

## Convención de nombres (recomendada)

- `bitacora_01.pdf` … `bitacora_05.pdf`
- `ficha_01.pdf` … `ficha_05.pdf`
- `faq_01.pdf` … `faq_05.pdf`

Así es fácil mapearlos en pruebas y en el análisis de patrones de encabezado.

Conviene validar igualmente contra **markdown de Docling** (fixture corto por familia de layout).
