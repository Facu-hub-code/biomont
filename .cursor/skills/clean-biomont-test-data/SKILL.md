---
name: clean-biomont-test-data
description: >-
  Limpia datos operativos de prueba en Postgres de Biomont (chats, tickets,
  decisiones del agente, documentos RAG, productos) con scripts/clean_test_data.sh.
  Usar cuando el usuario pida resetear la base de pruebas, vaciar chats/documentos,
  borrar tickets o decisiones de test, o empezar de cero en dev/QA. Requiere
  confirmación explícita antes de ejecutar el borrado.
---

# clean-biomont-test-data

Limpieza masiva de **datos operativos de prueba** en la base Postgres de Biomont
(Railway o local). No reemplaza migraciones ni backups; solo vacía tablas de
contenido generado en pruebas.

Scripts en la raíz del repo:

| Archivo | Rol |
|---------|-----|
| `scripts/clean_test_data.sh` | **Recomendado**: conteos, confirmación, `--dry-run` |
| `scripts/clean_test_data.sql` | SQL en una transacción (usado por el `.sh`) |
| `scripts/reset_operational_data.sh` | Mismo SQL, **sin** confirmación interactiva |

## Pre-requisitos

- `psql` instalado.
- `DATABASE_URL` en `.env` o inyectada con `railway run`.
- Para conexión local a Railway: el `.sh` usa `DATABASE_PUBLIC_URL` si
  `DATABASE_URL` apunta a `*.railway.internal` (misma heurística que
  `scripts/railway_psql.sh`).

Coordinar con **manage-biomont-db** para lecturas/inspección; esta skill es solo
para el flujo de limpieza.

## Qué borra / qué conserva

**Borra (TRUNCATE):**

- Chats: `conversations`, `messages`, `conversation_state`
- Agente: `agent_decisions`, `tickets`
- RAG: `documents` (+ cascada: `document_chunks`, `document_sections`,
  `knowledge_chunks`, `faq_entries`, `document_products`)
- Catálogo: `products`, `product_aliases`
- `bo_audit_log`

**No toca:**

- `countries`, `bo_users`, `rtc_users`, `rtc_user_countries`, `system_prompts`

## Flujo obligatorio para el agente

1. **Nunca** ejecutar el borrado sin que el usuario lo pida explícitamente en el chat.
2. **Siempre** correr primero `--dry-run` y mostrar la tabla de conteos al usuario.
3. Advertir que es **irreversible** (salvo backup/PITR) y confirmar entorno
   (dev/QA, no producción salvo orden explícita).
4. Ejecutar el borrado solo tras confirmación del usuario:
   - Interactivo: `./scripts/clean_test_data.sh` (el usuario escribe `si` en la terminal), **o**
   - No interactivo: `./scripts/clean_test_data.sh --yes` **solo** si el usuario
     confirmó en el chat (p. ej. "sí, limpiá la base de prueba").
5. Tras ejecutar, mostrar de nuevo los conteos (el script los imprime al final).

## Comandos

Desde la **raíz del repo**:

```bash
# Solo conteos (obligatorio como primer paso)
./scripts/clean_test_data.sh --dry-run
```

```bash
# Con confirmación en terminal
./scripts/clean_test_data.sh
```

```bash
# Sin prompt (solo si el usuario ya confirmó en el chat)
./scripts/clean_test_data.sh --yes
```

Con **Railway**:

```bash
railway run ./scripts/clean_test_data.sh --dry-run
railway run ./scripts/clean_test_data.sh --yes
```

SQL directo (evitar salvo que el usuario lo pida; sin preview integrado):

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/clean_test_data.sql
```

## Después de limpiar

Sugerir al usuario, si aplica:

- Re-sembrar productos: `python scripts/bootstrap_products.py` (o el flujo del repo).
- Crear admin si hace falta: `./scripts/seed_admin.sh`.
- System prompt: ya queda en DB; `scripts/seed_dev.sql` solo si hace falta v1.

## Reglas duras

- **NO** ejecutar en producción sin confirmación explícita + mención de backup.
- **NO** usar `DROP`/`TRUNCATE` ad-hoc en SQL; usar solo estos scripts.
- **NO** loguear `DATABASE_URL` en claro.
- **NO** confundir con borrar usuarios RTC/backoffice: esos datos se conservan.

## Anti-patterns

- Ejecutar `reset_operational_data.sh` sin avisar (no tiene confirmación).
- Borrar y asumir que el catálogo de productos sigue en YAML sin re-bootstrap.
- Modificar `clean_test_data.sql` para incluir `system_prompts` o `bo_users`.
