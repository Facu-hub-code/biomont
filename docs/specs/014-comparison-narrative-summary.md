# 014 - Comparador comercial: resumen narrativo (similitudes + diferencias)

## Contexto y objetivo

La spec [013](./013-comparison-llm-redactor.md) redujo el volcado Excel a bullets de diferencias tier 1–2. En WhatsApp el RTC sigue recibiendo listas extensas y **solo diferencias**, sin contexto de similitudes.

**Objetivo:** en modo `summary` (default), entregar **1–2 párrafos** que integren similitudes y diferencias clínicamente relevantes. Mantener `focus` y `full` sin cambios sustanciales.

**Migraciones necesarias:** no.

## Alcance

### En alcance

- Calcular `similarities[]` además de `differences[]` en `ComparisonRepository.diff_rows`.
- Enriquecer `ComparisonRedactorInput` con `similarity_items[]`.
- Modo `summary`: structured output con `paragraphs[]` (1–2) + `follow_up_hint` opcional.
- Fallback determinista narrativo (`format_comparison_narrative_brief`).
- Guardrails: longitud máxima, sin juicio de valor, números solo de snippets.

### Fuera de alcance

- Cambios en tablas `commercial_comparison_*`, import Excel o backoffice.
- Modo `focus` (sigue por columna) y `full` (listado completo).

## Criterios Given/When/Then

- **CA-1** — **Given** set publicado con similitudes tier 1–2 y diferencias tier 1–2, **When** `"MARVO 20 versus Marboxi"`, **Then** respuesta ≤ ~700 caracteres de cuerpo, 1–2 párrafos, menciona al menos una similitud y una diferencia, footer con versión.
- **CA-2** — **When** `"MARVO 20 vs Marboxi solo en dosis"`, **Then** modo `focus` sin cambios (1 eje).
- **CA-3** — **When** `"listame todas las diferencias"`, **Then** modo `full` (listado).
- **CA-4** — **Given** `AGENT_COMPARISON_LLM_REDACTOR=false`, **When** comparación summary, **Then** fallback narrativo determinista (no bullets).
- **CA-5** — **Given** LLM inventa cifra, **Then** fallback narrativo.

## Rollback

`AGENT_COMPARISON_LLM_REDACTOR=false` → narrativo determinista. Revertir commit de presenter/redactor.

## Archivos impactados

- `services/common/src/biomont_common/schemas/comparison.py`
- `services/common/src/biomont_common/db/comparison_repository.py`
- `services/common/src/biomont_common/comparison/presenter.py`
- `services/common/src/biomont_common/comparison/redactor_validate.py`
- `services/agent/src/app/agent/prompts/comparison_redactor.py`
- `services/agent/src/app/agent/graph/nodes/comparison_redactor.py`
- Tests en `services/common/tests/` y `services/agent/tests/`
