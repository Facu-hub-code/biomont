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
| 007 | [Eliminar atajo FAQ, intent `faq` e ingest legacy](./007-remove-faq-shortcut-and-legacy-ingest.md) | implementada |
| 008 | [Configuración del agente en DB: top-k, intenciones y prompts](./008-agent-config-from-backoffice-db.md) | implementada |
| 009 | [Backoffice UX: volver atrás, búsqueda y formularios colapsables](./009-backoffice-catalog-ux-search-and-forms.md) | implementada |
| 010 | [Decisiones del agente: BFF, nombres legibles y vista previa de chunks](./010-agent-decisions-detail-bff-enrichment.md) | implementada |
| 011 | [Motor de calculo de dosis (datos estructurados + backoffice)](./011-dose-calculation-engine.md) | en curso |
| 012 | [Comparador comercial (columnas dinamicas por documento)](./012-competitor-comparison-hybrid.md) | en curso |
| 013 | [Comparador comercial: redaccion con LLM (diff determinista)](./013-comparison-llm-redactor.md) | en curso |
| 014 | [Comparador comercial: resumen narrativo (similitudes + diferencias)](./014-comparison-narrative-summary.md) | implementada |
| 016 | [Comparador comercial: prioridad de columnas desde backoffice](./016-comparison-column-priority.md) | implementada |
| 017 | [Webhook WhatsApp: idempotencia (wamid) y ack rapido](./017-whatsapp-webhook-idempotency.md) | implementada |

## Reglas de calidad

- Una sola responsabilidad por spec.
- Criterios Given/When/Then testeables, sin ambiguedad.
- Indicar observabilidad y rollback.
- Para cambios DB: marcar `Migraciones necesarias: si/no` y referenciar los
  scripts en `migrations/`.
- Referenciar archivos impactados cuando ya se conozcan.
