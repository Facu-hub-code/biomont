---
name: manage-biomont-db
description: >-
  Operaciones agenticas sobre la base Postgres + pgvector de Biomont alojada
  en Railway. Cubre listado de tablas, descripcion de schema, aplicacion de
  migraciones versionadas, inspeccion de chunks/embeddings y backups
  rapidos. Usar siempre que el agente necesite leer o modificar la BDD del
  proyecto. NO ejecutar DROP/TRUNCATE sin confirmacion explicita del usuario.
---

# manage-biomont-db

Skill para operar contra la base de datos Postgres+pgvector del proyecto
**Biomont** que vive en Railway. Toda la conexion sale por `DATABASE_URL` o
por el CLI de Railway (`railway run`).

## Pre-requisitos

- `psql` instalado en local.
- `railway` CLI instalado y autenticado en el proyecto correcto:
  `railway link` y luego `railway status` para verificar.
- `DATABASE_URL` exportada **o** usar siempre `railway run` para inyectarla.

## Patrones canonicos

### 1. Listar tablas

```bash
railway run psql -c "\dt"
```

o:

```bash
psql "$DATABASE_URL" -c "\dt"
```

### 2. Describir una tabla

```bash
railway run psql -c "\d+ public.documents"
```

### 3. Aplicar migracion versionada

Toda migracion vive en `migrations/NNN_*.sql` y se aplica con:

```bash
railway run ./scripts/apply_migration.sh 001
```

Para revertir manualmente (si existe el `.down.sql`):

```bash
railway run ./scripts/apply_migration.sh 001 --down
```

El script:

- exige `DATABASE_URL`,
- ejecuta en una sola transaccion,
- aborta al primer error.

### 4. Inspeccionar `document_chunks`

Conteo y dimensiones del vector:

```bash
railway run psql -c "
  SELECT count(*) AS chunks,
         count(DISTINCT document_id) AS documents
  FROM public.document_chunks;
"
```

Verificar dimension del embedding (debe ser 1536):

```bash
railway run psql -c "
  SELECT array_length(embedding::real[], 1) AS dim
  FROM public.document_chunks
  LIMIT 1;
"
```

Top similitud para una consulta de prueba (requiere setear `:q` desde el
shell con el embedding ya calculado; no se hace de memoria):

```bash
railway run psql -c "
  SELECT d.title,
         1 - (c.embedding <=> :'query_embedding') AS similarity,
         left(c.content, 120) AS preview
  FROM public.document_chunks c
  JOIN public.documents d ON d.id = c.document_id
  ORDER BY c.embedding <=> :'query_embedding'
  LIMIT 5;
"
```

### 5. Backup rapido a archivo local

```bash
railway run pg_dump --no-owner --format=custom \
    --file "./backups/biomont_$(date +%Y%m%d_%H%M).dump"
```

### 6. Validar extension `vector`

```bash
railway run psql -c "
  SELECT extname, extversion
  FROM pg_extension
  WHERE extname IN ('vector', 'pgcrypto');
"
```

## Reglas duras

- **NO** ejecutar `DROP DATABASE`, `DROP SCHEMA`, `DROP TABLE` ni
  `TRUNCATE` sin que el usuario lo pida explicitamente en el chat.
- **NO** modificar `system_prompts` por SQL directo: hacerlo siempre por
  el backoffice para que quede audit log.
- Toda nueva migracion debe agregarse como `NNN_*.sql` con su
  `NNN_*.down.sql` correspondiente.
- Antes de aplicar una migracion contra la DB, verificar con `psql -1
  --file ... --set ON_ERROR_STOP=on` si hay dudas, o aplicar primero a
  una rama de Railway si esta disponible.
- Nunca loguear `DATABASE_URL` en claro. El script
  `apply_migration.sh` ya enmascara la password.

## Anti-patterns

- Conectarse con superusuario ad-hoc desde codigo de aplicacion.
- Usar `langchain_postgres.PGVector` con una collection nueva por cada
  carga (rompe el filtrado por `country_iso`). Usar siempre la tabla
  custom `document_chunks`.
- Crear indices `IVFFlat` antes de tener ~1000 vectores; usar
  `HNSW` o aplazar la creacion segun el volumen.
