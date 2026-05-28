-- =====================================================================
-- 007_drop_faq_and_legacy_chunks.down.sql
-- Recrea tablas eliminadas por 007 (solo DDL, sin datos).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.document_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    token_count integer NOT NULL DEFAULT 0,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document
    ON public.document_chunks (document_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
    ON public.document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS public.faq_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id uuid REFERENCES public.products(id) ON DELETE SET NULL,
    document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    question text NOT NULL,
    normalized_question text GENERATED ALWAYS AS
        (public.immutable_unaccent_lower(question)) STORED,
    answer text NOT NULL,
    embedding vector(1536) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS
        (to_tsvector('spanish', coalesce(question, '') || ' ' || coalesce(answer, ''))) STORED,
    source_page integer,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_faq_entries_norm_trgm
    ON public.faq_entries USING gin (normalized_question gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_faq_entries_tsv
    ON public.faq_entries USING gin (tsv);

CREATE INDEX IF NOT EXISTS idx_faq_entries_embedding_hnsw
    ON public.faq_entries
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_faq_entries_product
    ON public.faq_entries (product_id);

COMMIT;
