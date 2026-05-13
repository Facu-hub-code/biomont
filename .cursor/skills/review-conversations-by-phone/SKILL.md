---
name: review-conversations-by-phone
description: >-
  Consultar Postgres (Railway) para revisar conversaciones y mensajes filtrados
  por número de teléfono del RTC (`rtc_users.phone_e164`). Incluye SQL de
  descubrimiento, normalización dígitos vs E.164, hilo por conversación y
  decisiones del agente. Usar cuando haga falta soporte/debug por WhatsApp sin
  pasar solo por la UI del backoffice. Requiere DATABASE_URL / railway run;
  coordina operaciones pesadas con manage-biomont-db.
---

# Revisar conversaciones por número de teléfono

## Relación de datos

- **`public.rtc_users`**: un RTC por cliente WhatsApp — columna **`phone_e164`** (`text NOT NULL UNIQUE`). También **`name`**, **`enabled`**, **`id`** (uuid).
- **`public.conversations`**: `rtc_user_id` → `rtc_users.id`; orden útil **`last_message_at DESC`**.
- **`public.messages`**: mensajes por conversación (`conversation_id`), **`role`** (`user` \| `assistant` \| `system`), **`content`**, **`created_at`**.
- Opcional **`public.agent_decisions`**: enlazadas a **`message_id`** cuando existió decisión registrada (`decision`, `reasoning`, `top_similarity`, …).

Esquema versionado en `migrations/001_extensions_and_core.sql` (RTC + `phone_e164`) y `migrations/003_conversations_tickets.sql` (conversaciones/mensajes). Consultas espéjo similares al repo `ConversationAdminRepository` en `services/backoffice-api`.

## Pre-requisitos y conexión

Ver [`manage-biomont-db`](../manage-biomont-db/SKILL.md):

- **`psql`** y **`DATABASE_URL`** en entorno **o** `railway run` desde el proyecto enlazado.
- Ejecutar siempre estos `SELECT` de **solo lectura** salvo que el usuario pida cambios explícitos.

Patrón habitual (raíz del monorepo o donde esté cargado `.env`):

```bash
psql "$DATABASE_URL" -c "..."
```

```bash
railway run psql -c "..."
```

## Normalización del número en consultas

En BD el valor puede guardarse como **`5491122334455`** o **`+5491122334455`** (convención del negocio al dar de alta RTCs). Meta/WhatsApp suele usar **solo dígitos** al enviar. Para comparar sin ambigüedad, igualar solo dígitos:

```sql
regexp_replace(u.phone_e164, '\D', '', 'g')
```

Tu literal de búsqueda debe ser **solo dígitos** (sin `+` ni espacios).

## Privacidad

- No pegar números completos ni contenido de chats en hilos públicos si el usuario pidió anonimizado; usar sufijos tipo `***7788` o `request_id`.
- No volcar **`DATABASE_URL`** en logs ni en el chat.

---

## 1) Localizar RTC(s) por teléfono

**Coincidencia exacta en dígitos** (sustituir `5491122334455` por el caso real):

```sql
SELECT u.id AS rtc_user_id,
       u.name,
       u.phone_e164,
       u.enabled,
       u.created_at
FROM public.rtc_users u
WHERE regexp_replace(u.phone_e164, '\D', '', 'g') = '5491122334455';
```

**Búsqueda parcial** (últimos N dígitos; ej. terminación):

```sql
SELECT u.id, u.name, u.phone_e164, u.enabled
FROM public.rtc_users u
WHERE regexp_replace(u.phone_e164, '\D', '', 'g') LIKE '%7788';
```

Sin índice funcional específico, `LIKE '%…'` puede ser costoso en tablas grandes; para un único soporte puntual suele bastar.

## 2) Conversaciones de ese RTC

Sustituir `'<uuid_rtc_user>'` por el resultado de **`rtc_user.id`** anterior:

```sql
SELECT c.id AS conversation_id,
       c.started_at,
       c.last_message_at
FROM public.conversations c
WHERE c.rtc_user_id = '<uuid_rtc_user>'::uuid
ORDER BY c.last_message_at DESC
LIMIT 50;
```

## 3) Mensajes de una conversación

Sustituir `'<uuid_conversation>'`:

```sql
SELECT m.created_at,
       m.role::text AS role,
       left(m.content, 280) AS content_preview,
       m.id AS message_id
FROM public.messages m
WHERE m.conversation_id = '<uuid_conversation>'::uuid
ORDER BY m.created_at ASC, m.id ASC;
```

Para ver **todo** el cuerpo (puede ser muy largo), quitar **`left(...)`** y exportar solo en entorno seguro:

```bash
railway run psql -c "COPY (SELECT ...) TO STDOUT WITH CSV HEADER" > /tmp/messages_export.csv
```

(solo si el usuario lo autoriza y el destino es adecuado).

## 4) Decisiones del agente enlazadas al hilo

Misma conversación (`conversation_id`). Join por mensajes pertenecientes a esa conversación:

```sql
SELECT m.created_at,
       m.role::text AS role,
       ad.decision::text AS decision,
       ad.top_similarity,
       left(coalesce(ad.reasoning, ''), 200) AS reasoning_preview,
       m.id AS message_id
FROM public.messages m
LEFT JOIN public.agent_decisions ad ON ad.message_id = m.id
WHERE m.conversation_id = '<uuid_conversation>'::uuid
ORDER BY m.created_at ASC, m.id ASC;
```

## 5) Query todo-en-uno (teléfono en dígitos → últimas conversaciones + preview último mensaje)

Sustituir solo el literal **`'5491122334455'`**:

```sql
WITH u AS (
  SELECT *
  FROM public.rtc_users r
  WHERE regexp_replace(r.phone_e164, '\D', '', 'g') = '5491122334455'
),
c AS (
  SELECT cv.*
  FROM public.conversations cv
  JOIN u ON u.id = cv.rtc_user_id
  ORDER BY cv.last_message_at DESC
  LIMIT 20
)
SELECT c.id AS conversation_id,
       c.last_message_at,
       lm.preview AS last_message_preview,
       u.phone_e164
FROM c
JOIN u ON true
LEFT JOIN LATERAL (
  SELECT m.content AS preview
  FROM public.messages m
  WHERE m.conversation_id = c.id
  ORDER BY m.created_at DESC
  LIMIT 1
) lm ON true
ORDER BY c.last_message_at DESC;
```

---

## Coordinación con otras skills

- Operaciones DDL, migraciones, backups: [`manage-biomont-db`](../manage-biomont-db/SKILL.md).
- Logs de runtime local (Compose): [`review-docker-compose-local`](../review-docker-compose-local/SKILL.md).
- **`NO`** ejecutar `DELETE`/`UPDATE` masivos sobre `messages` / `conversations` sin pedido explícito del usuario; preferir lectura.
