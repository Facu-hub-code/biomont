-- 015: Idempotencia de webhooks WhatsApp (wamid).

BEGIN;

CREATE TABLE IF NOT EXISTS public.whatsapp_inbound_messages (
    provider_message_id text PRIMARY KEY,
    from_phone_e164 text NOT NULL,
    message_type text NOT NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processed', 'skipped')),
    received_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_inbound_received
    ON public.whatsapp_inbound_messages (received_at DESC);

COMMENT ON TABLE public.whatsapp_inbound_messages IS
    'Dedupe de eventos Meta WhatsApp Cloud API por message.id (wamid).';

COMMIT;
