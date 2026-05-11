-- =====================================================================
-- 002_rag.down.sql
-- Rollback manual de la migracion 002.
-- =====================================================================

BEGIN;

DROP INDEX IF EXISTS public.idx_document_chunks_embedding_hnsw;
DROP INDEX IF EXISTS public.idx_document_chunks_document;
DROP TABLE IF EXISTS public.document_chunks;

DROP TRIGGER IF EXISTS trg_documents_updated_at ON public.documents;
DROP INDEX IF EXISTS public.uq_documents_content_sha;
DROP INDEX IF EXISTS public.idx_documents_status;
DROP INDEX IF EXISTS public.idx_documents_country;
DROP TABLE IF EXISTS public.documents;
DROP TYPE  IF EXISTS public.document_status;

COMMIT;
