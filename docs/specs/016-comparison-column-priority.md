# 016 - Prioridad de columnas del comparador comercial (backoffice)

## Contexto y objetivo

El resumen del comparador (modo `summary`) elige hasta N ejes según un mapa fijo
en código (`tier_for_column_key`). Productos como Proteggo priorizan columnas distintas
(p. ej. tiempo de efecto, forma farmacéutica) que no coinciden con el default global.

**Objetivo:** permitir marcar desde el backoffice qué columnas del cuadro Excel son
**prioritarias** para el agente, por producto/set comparativo.

## Alcance / fuera de alcance

- **En alcance:** columna `display_tier` en `commercial_comparison_columns`; API GET/PUT
  por producto; UI en ficha de producto; agente usa tier publicado al armar summary.
- **Fuera de alcance:** aliases de foco por columna; reordenar columnas del Excel; matriz ESPECTRO.

## Requisitos funcionales

- RF-1: Tras importar Excel, cada columna tiene `display_tier` (default desde heurística global).
- RF-2: Admin/científico puede marcar columnas como prioritarias (tier 1) desde BO.
- RF-3: Al publicar, se copia `display_tier` a la versión publicada.
- RF-4: El agente ordena y filtra summary por `display_tier` de la versión publicada.

## Criterios de aceptacion

- **CA-1** — **Given** set Proteggo con columnas marcadas prioritarias, **When** comparación summary,
  **Then** la respuesta incluye esos ejes antes que precauciones/país.
- **CA-2** — **When** PUT columnas sin set importado, **Then** 404.

## Migraciones necesarias

`Migraciones necesarias: si` — `migrations/014_comparison_column_config.sql`

## Archivos impactados

- `services/common` — schemas, `comparison_repository`, `presenter`
- `services/backoffice-api` — router, admin repository
- `services/backoffice-web` — formulario en ficha producto
