# NNN - Titulo de la feature

> Plantilla obligatoria para nuevas specs. Copiar a `NNN-nombre-feature.md` y
> completar todas las secciones. No reemplazar secciones obligatorias por
> resumenes vagos.

## Contexto y objetivo

Que problema resolvemos y por que.

## Alcance / fuera de alcance

- **En alcance**: ...
- **Fuera de alcance**: ...

## Requisitos funcionales

- RF-1: ...
- RF-2: ...

## Requisitos no funcionales

- RNF-1: rendimiento, latencia objetivo.
- RNF-2: seguridad, privacidad, multi-tenant.
- RNF-3: observabilidad esperada.

## Criterios de aceptacion (Given/When/Then)

- **CA-1**
  - **Given** ...
  - **When** ...
  - **Then** ...

## Diseno tecnico

Resumen de arquitectura, archivos impactados, decisiones de diseno.

## Migraciones necesarias

`Migraciones necesarias: si/no`

Si **si**:

- Script: `migrations/NNN_*.sql` (+ `.down.sql`).
- Evidencia de estructura actual obtenida via skill `manage-biomont-db` (no
  solo la intencion).

## Plan de pruebas

- Tests unitarios: ...
- Tests de integracion: ...
- Tests HTTP (endpoints): caso exitoso + error principal.
- Mocks para LLM/WhatsApp/Docling.

## Observabilidad

- Logs estructurados: `component`, `event`, `request_id`, ...
- Metricas/alarmas nuevas: ...

## Riesgos y rollback

- Riesgo: ... | Mitigacion: ...
- Rollback: pasos exactos para revertir (DB + codigo).
