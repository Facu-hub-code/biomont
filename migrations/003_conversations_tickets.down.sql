-- =====================================================================
-- 003_conversations_tickets.down.sql
-- Rollback manual de la migracion 003.
-- =====================================================================

BEGIN;

DROP TRIGGER IF EXISTS trg_tickets_updated_at ON public.tickets;
DROP INDEX IF EXISTS public.idx_tickets_status;
DROP TABLE IF EXISTS public.tickets;
DROP TYPE  IF EXISTS public.ticket_status;
DROP TYPE  IF EXISTS public.ticket_type;

DROP INDEX IF EXISTS public.idx_agent_decisions_decision;
DROP TABLE IF EXISTS public.agent_decisions;
DROP TYPE  IF EXISTS public.agent_decision_kind;

DROP INDEX IF EXISTS public.idx_messages_conversation;
DROP TABLE IF EXISTS public.messages;
DROP TYPE  IF EXISTS public.message_role;

DROP INDEX IF EXISTS public.idx_conversations_rtc;
DROP TABLE IF EXISTS public.conversations;

DROP INDEX IF EXISTS public.uq_system_prompts_active;
DROP TABLE IF EXISTS public.system_prompts;

COMMIT;
