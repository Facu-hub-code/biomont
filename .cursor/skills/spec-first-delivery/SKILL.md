---
name: spec-first-delivery
description: >-
  Impone entrega spec-first: obliga a definir o actualizar una spec en docs/specs
  antes de implementar código de feature, con requisitos, criterios Given/When/Then,
  pruebas, riesgos/rollback y coordinación de migraciones DB sobre PostgreSQL
  (conexión vía DATABASE_URL / Railway). Usar cuando se pidan features nuevas,
  cambios de comportamiento, refactors funcionales o cambios de base de datos.
---

# Spec-First Delivery

## Política obligatoria

Antes de escribir o modificar código de feature, crear o actualizar una spec en `docs/specs/`.

**Base obligatoria** (leer al iniciar):

- [`docs/specs/README.md`](../../../docs/specs/README.md)
- [`docs/specs/spec-template.md`](../../../docs/specs/spec-template.md)

Para **inspección y migraciones de PostgreSQL**, usar la skill [`manage-biomont-db`](../manage-biomont-db/SKILL.md): conexión por `DATABASE_URL` o `railway run`, sin MCP dedicado.

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
   - **antes** de definir el cambio, obtener estructura real con `psql` (ver sección siguiente y `manage-biomont-db`). Requisitos: `psql` y `DATABASE_URL` en entorno **o** `railway run` con el proyecto enlazado.
   - si es **sí**, crear script de migración versionado según convención del repo (`migrations/NNN_*.sql`)
4. **Implementar** en pasos pequeños mapeados a criterios de aceptación de la spec.
5. **Validar** la evidencia final (comportamiento, pruebas, migraciones) contra la spec.

## Consultas y comandos para evidencia de esquema (PostgreSQL)

Usar uno de estos patrones de invocación:

```bash
psql "$DATABASE_URL" -c "..."
```

```bash
railway run psql -c "..."
```

**Listado rápido de tablas en `public`** (equivale a `\dt public.*`):

```sql
SELECT tablename
FROM pg_catalog.pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

**Columnas de una tabla** (cambiar el literal `'documents'` por el nombre real):

```sql
SELECT column_name, data_type, udt_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'documents'
ORDER BY ordinal_position;
```

Ejemplo en línea:

```bash
railway run psql -c "
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'documents'
ORDER BY ordinal_position;
"
```

**Índices de una tabla** (mismo literal de nombre):

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'documents';
```

**Constraints de una tabla**:

```sql
SELECT c.conname, c.contype, pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
JOIN pg_class rel ON rel.oid = c.conrelid
JOIN pg_namespace n ON n.oid = rel.relnamespace
WHERE n.nspname = 'public' AND rel.relname = 'documents';
```

**Extensiones instaladas** (útil si la spec toca vectores u otras):

```sql
SELECT extname, extversion FROM pg_extension ORDER BY extname;
```

Documentar en la spec la salida relevante (tablas/columnas/constraints consultados), no solo la intención del cambio.

## Reglas de calidad de spec

- Una sola responsabilidad por spec.
- Criterios testeables, sin ambigüedad.
- Incluir observabilidad y rollback.
- Referenciar archivos impactados cuando ya se conozcan.
- Para cambios DB: incluir **evidencia de estructura** obtenida con `psql` o las queries anteriores (o resumen fiel de la salida), no solo la intención.

## Criterio de bloqueo

Si **no existe** spec en `docs/specs/` que cubra el cambio solicitado (o no está actualizada de forma coherente con el alcance pedido), **detener la implementación** y crear o actualizar la spec **primero**.

Usar el [spec-template](../../../docs/specs/spec-template.md) como checklist; no sustituir secciones obligatorias por resúmenes vagos.
