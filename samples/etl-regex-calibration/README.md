# Calibración de regex ETL (bitácora / ficha técnica / FAQ)

Coloca aquí los PDFs de referencia para afinar `StructuredMarkdownChunker`
(`services/common/src/biomont_common/integrations/text_splitter.py`).

## Estructura

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

## Privacidad y Git

Si los PDFs son confidenciales, **no** hagas commit de esta carpeta: añadí solo `.gitkeep`
en subcarpetas vacías; los binarios los agregás vos localmente o usá
`git update-index --skip-worktree` / entrada en `.gitignore` conforme a la política del equipo.

## Siguiente paso

Hay un análisis de patrones sobre los PDF cargados en el repo:

- [ANALISIS_PATRONES_SECCIONES.md](./ANALISIS_PATRONES_SECCIONES.md)

Conviene validar igualmente contra **markdown de Docling** (fixture corto por familia de layout).
