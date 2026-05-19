-- =====================================================================
-- clean_test_data.sql
--
-- Borra datos operativos de prueba generados en desarrollo/QA:
--   chats (conversations, messages, conversation_state)
--   tickets, agent_decisions
--   documentos (chunks, secciones, FAQ, vínculos N:M)
--   productos y aliases
--   bo_audit_log
--
-- NO toca: countries, bo_users, rtc_users, rtc_user_countries, system_prompts
--
-- Uso directo:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/clean_test_data.sql
--
-- Preferir el wrapper con confirmación:
--   ./scripts/clean_test_data.sh
--   ./scripts/clean_test_data.sh --yes
-- =====================================================================

BEGIN;

-- Chats y trazabilidad del agente
TRUNCATE TABLE
  public.tickets,
  public.agent_decisions,
  public.conversation_state,
  public.messages,
  public.conversations
RESTART IDENTITY CASCADE;

-- Documentos + knowledge (document_chunks, document_sections, knowledge_chunks,
-- faq_entries, document_products vía CASCADE)
TRUNCATE TABLE public.documents RESTART IDENTITY CASCADE;

-- Catálogo de productos (product_aliases, document_products restantes vía CASCADE)
TRUNCATE TABLE public.products RESTART IDENTITY CASCADE;

-- Auditoría del backoffice
TRUNCATE TABLE public.bo_audit_log RESTART IDENTITY;

COMMIT;
