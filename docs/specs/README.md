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
| 002 | [Vista espejo de conversaciones y playground del agente](./002-agent-conversations-mirror-and-playground.md) | borrador |
| 003 | [Grafo LangGraph + retrieval hibrido + reestructuracion de conocimiento](./003-langgraph-hybrid-rag-and-knowledge-restructure.md) | implementada (pending: ingest del corpus real) |
| 004 | [Backoffice: productos, documentos (chunks) y auditoria de agent-decisions](./004-backoffice-products-documents-and-agent-decisions.md) | implementada |
| 005 | [Backoffice web: feedback async y estados de carga (toast/loading)](./005-backoffice-async-feedback-and-loading-states.md) | implementada |
| 006 | [Backoffice: vinculacion producto ↔ documento (N:M)](./006-backoffice-product-document-links.md) | implementada |

## Reglas de calidad

- Una sola responsabilidad por spec.
- Criterios Given/When/Then testeables, sin ambiguedad.
- Indicar observabilidad y rollback.
- Para cambios DB: marcar `Migraciones necesarias: si/no` y referenciar los
  scripts en `migrations/`.
- Referenciar archivos impactados cuando ya se conozcan.
