-- =====================================================================
-- 007_drop_faq_and_legacy_chunks.sql
-- Elimina faq_entries y document_chunks (spec 007).
-- =====================================================================

BEGIN;

DROP TABLE IF EXISTS public.faq_entries;
DROP TABLE IF EXISTS public.document_chunks;

COMMIT;
