-- 015 down: quitar dedupe WhatsApp.

BEGIN;

DROP TABLE IF EXISTS public.whatsapp_inbound_messages;

COMMIT;
