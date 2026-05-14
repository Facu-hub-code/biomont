-- =====================================================================
-- 004_knowledge_restructure.down.sql
-- Rollback de la migracion 004.
-- ATENCION: destruye datos en knowledge_chunks, faq_entries,
-- document_sections, conversation_state, products, product_aliases.
-- document_chunks NO se toca (siguio activo por feature flag).
-- =====================================================================

BEGIN;

ALTER TABLE public.agent_decisions
    DROP COLUMN IF EXISTS graph_trace;

DROP TRIGGER IF EXISTS trg_conversation_state_updated_at ON public.conversation_state;
DROP INDEX IF EXISTS public.idx_conversation_state_product;
DROP TABLE IF EXISTS public.conversation_state;

DROP INDEX IF EXISTS public.idx_faq_entries_product;
DROP INDEX IF EXISTS public.idx_faq_entries_embedding_hnsw;
DROP INDEX IF EXISTS public.idx_faq_entries_tsv;
DROP INDEX IF EXISTS public.idx_faq_entries_norm_trgm;
DROP TABLE IF EXISTS public.faq_entries;

DROP INDEX IF EXISTS public.idx_knowledge_chunks_embedding_hnsw;
DROP INDEX IF EXISTS public.idx_knowledge_chunks_tsv;
DROP INDEX IF EXISTS public.idx_knowledge_chunks_kind_section;
DROP INDEX IF EXISTS public.idx_knowledge_chunks_product_kind;
DROP INDEX IF EXISTS public.idx_knowledge_chunks_document;
DROP TABLE IF EXISTS public.knowledge_chunks;

DROP INDEX IF EXISTS public.idx_document_sections_document;
DROP TABLE IF EXISTS public.document_sections;

DROP INDEX IF EXISTS public.idx_documents_kind;
DROP INDEX IF EXISTS public.idx_documents_product;
ALTER TABLE public.documents DROP COLUMN IF EXISTS product_id;
ALTER TABLE public.documents DROP COLUMN IF EXISTS kind;

DROP TRIGGER IF EXISTS trg_products_updated_at ON public.products;
DROP INDEX IF EXISTS public.idx_product_aliases_product;
DROP INDEX IF EXISTS public.idx_product_aliases_norm_trgm;
DROP TABLE IF EXISTS public.product_aliases;

DROP INDEX IF EXISTS public.uq_products_name_country;
DROP TABLE IF EXISTS public.products;

DROP TYPE IF EXISTS public.document_kind;

DROP FUNCTION IF EXISTS public.immutable_unaccent_lower(text);

-- pg_trgm y unaccent las dejamos: pueden tener otros consumidores fuera de
-- esta spec. Si se quiere remover explicitamente, hacerlo a mano.

COMMIT;
