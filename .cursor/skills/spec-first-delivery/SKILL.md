---
name: spec-first-delivery
description: >-
  Impone entrega spec-first: obliga a definir o actualizar una spec en docs/specs
  antes de implementar código de feature, con requisitos, criterios Given/When/Then,
  pruebas, riesgos/rollback y coordinación de migraciones DB consultando el esquema
  vía MCP (Supabase). Usar cuando se pidan features nuevas, cambios de comportamiento,
  refactors funcionales o cambios de base de datos.
---

# Spec-First Delivery

## Política obligatoria

Antes de escribir o modificar código de feature, crear o actualizar una spec en `docs/specs/`.

**Base obligatoria** (leer al iniciar):

- [`docs/specs/README.md`](../../../docs/specs/README.md)
- [`docs/specs/spec-template.md`](../../../docs/specs/spec-template.md)

## Flujo obligatorio

1. **Definir la spec primero** en `docs/specs/NNN-nombre-feature.md` (número `NNN` acorde a convención del repo y `README` de specs).
2. **Completar como mínimo**:
   - contexto y objetivo
   - alcance / fuera de alcance
   - requisitos funcionales y no funcionales
   - criterios Given/When/Then
   - plan de pruebas
   - riesgos y rollback
3. **Confirmar si hay cambios DB**:
   - marcar explícitamente: **Migraciones necesarias: sí / no**
   - consultar estructura actual vía MCP del proyecto (`plugin-supabase-supabase`): `list_tables` y, si hace falta, `execute_sql` **antes** de definir el cambio
   - si es **sí**, crear script de migración versionado según convención del repo
4. **Implementar** en pasos pequeños mapeados a criterios de aceptación de la spec.
5. **Validar** la evidencia final (comportamiento, pruebas, migraciones) contra la spec.

## Reglas de calidad de spec

- Una sola responsabilidad por spec.
- Criterios testeables, sin ambigüedad.
- Incluir observabilidad y rollback.
- Referenciar archivos impactados cuando ya se conozcan.
- Para cambios DB: incluir en la spec **evidencia de estructura** obtenida por MCP (tablas/columnas relevantes o resultado consultado), no solo la intención.

## Criterio de bloqueo

Si **no existe** spec en `docs/specs/` que cubra el cambio solicitado (o no está actualizada de forma coherente con el alcance pedido), **detener la implementación** y crear o actualizar la spec **primero**.

Usar el [spec-template](../../../docs/specs/spec-template.md) como checklist; no sustituir secciones obligatorias por resúmenes vagos.
