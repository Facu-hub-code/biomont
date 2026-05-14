-- =====================================================================
-- reset_operational_data.sql
--
-- PELIGRO: borra datos operativos (conversaciones, RAG, productos,
-- auditoria del backoffice) para pruebas desde cero.
--
-- NO ejecutar en produccion salvo PITR/backup y criterio explicito.
--
-- Deja intactos (entre otros):
--   public.countries, public.bo_users, public.rtc_users,
--   public.rtc_user_countries, public.system_prompts
--
-- Uso local (repo root, .env con DATABASE_URL):
--   set -a && . ./.env && set +a && psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/reset_operational_data.sql
--
-- Railway (con URL publica o proxy que resuelva el host):
--   railway run psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/reset_operational_data.sql
--
-- Ver tambien: scripts/reset_operational_data.sh
-- =====================================================================

BEGIN;

-- Conversaciones, mensajes, decisiones del agente, tickets, memoria de conversacion
TRUNCATE TABLE
  public.tickets,
  public.agent_decisions,
  public.conversation_state,
  public.messages,
  public.conversations
RESTART IDENTITY CASCADE;

-- Documentos y vectorizaciones (cascada: legacy chunks, secciones, knowledge, FAQ)
TRUNCATE TABLE public.documents RESTART IDENTITY CASCADE;

-- Catalogo de productos y aliases
TRUNCATE TABLE public.products RESTART IDENTITY CASCADE;

-- Auditoria de acciones del backoffice
TRUNCATE TABLE public.bo_audit_log RESTART IDENTITY;

COMMIT;
