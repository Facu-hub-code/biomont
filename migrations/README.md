# Migraciones SQL

Migraciones versionadas que se aplican manualmente desde local contra el
Postgres en Railway.

## Convencion

- `NNN_nombre.sql`: migracion "up".
- `NNN_nombre.down.sql`: rollback manual asociado.
- Aplicar con `scripts/apply_migration.sh NNN` (o `--down`).
- Cada `*.sql` debe ser **idempotente** cuando sea razonable (`IF NOT
  EXISTS`, `CREATE OR REPLACE`, etc.).

## Indice

| Numero | Archivo | Resumen |
| --- | --- | --- |
| 001 | [001_extensions_and_core.sql](./001_extensions_and_core.sql) | Extensiones pgvector/pgcrypto, catalogo paises, RBAC backoffice, RTCs WhatsApp |
| 002 | [002_rag.sql](./002_rag.sql) | Tabla `documents`, `document_chunks` con `vector(1536)` e indice |
| 003 | [003_conversations_tickets.sql](./003_conversations_tickets.sql) | `system_prompts`, conversaciones, mensajes, `agent_decisions`, tickets |
| 004 | [004_knowledge_restructure.sql](./004_knowledge_restructure.sql) | Productos, aliases, `knowledge_chunks`, FAQ, grafo |
| 006 | [006_product_document_links.sql](./006_product_document_links.sql) | Tabla puente `document_products` (N:M producto-documento) |
