# Specs de Biomont

Este directorio contiene la documentacion **spec-first** del proyecto. Antes de
implementar o modificar una feature, hay que crear o actualizar una spec en
este directorio.

## Convencion de archivos

- Las specs viven en `docs/specs/NNN-nombre-feature.md`.
- `NNN` es un numero consecutivo de 3 digitos (`001`, `002`, ...).
- Una spec por feature/cambio funcional. Si la feature es muy grande, dividir
  en sub-specs (`002a-...`, `002b-...`) con un indice en la spec madre.
- Usar el [`spec-template.md`](./spec-template.md) como checklist obligatoria.

## Indice

| ID | Titulo | Estado |
| --- | --- | --- |
| 001 | [Foundation v1: bootstrap, RAG, agente WhatsApp, backoffice](./001-foundation-v1.md) | en curso |

## Reglas de calidad

- Una sola responsabilidad por spec.
- Criterios Given/When/Then testeables, sin ambiguedad.
- Indicar observabilidad y rollback.
- Para cambios DB: marcar `Migraciones necesarias: si/no` y referenciar los
  scripts en `migrations/`.
- Referenciar archivos impactados cuando ya se conozcan.
