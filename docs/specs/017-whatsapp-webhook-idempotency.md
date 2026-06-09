# 017 — Webhook WhatsApp: idempotencia y ack rapido

## Problema

Meta reintenta el webhook si la respuesta tarda. El agente procesaba el mensaje
de forma sincrona antes de devolver `200`, sin deduplicar por `message.id`
(wamid). Eso generaba mensajes duplicados en el backoffice y respuestas dobles
al usuario.

## Solucion

1. **Ack rapido:** validar firma, parsear payload y encolar procesamiento con
   `BackgroundTasks`; responder `200` de inmediato.
2. **Idempotencia:** tabla `whatsapp_inbound_messages` con PK en
   `provider_message_id`. El worker hace `INSERT ... ON CONFLICT DO NOTHING`
   antes de invocar al orchestrator.

## Migraciones

- `migrations/015_whatsapp_inbound_dedup.sql`

## Criterios

- **Given** un POST valido con wamid nuevo, **When** llega el webhook,
  **Then** responde `200` con `enqueued: 1` y el orchestrator procesa una vez.
- **Given** el mismo wamid reenviado por Meta, **When** llega el segundo POST,
  **Then** responde `200` pero el orchestrator no vuelve a procesar el mensaje.
- **Given** un mensaje sin `id`, **When** llega el webhook, **Then** se procesa
  sin dedupe (log de advertencia).

## Rollback

Aplicar `migrations/015_whatsapp_inbound_dedup.down.sql`. Volver al handler
sincronico previo si hiciera falta.

## Archivos

- `services/agent/src/app/api/whatsapp_router.py`
- `services/agent/src/app/services/whatsapp_inbound_processor.py`
- `services/common/src/biomont_common/db/whatsapp_inbound_repository.py`
