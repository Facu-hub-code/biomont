-- =====================================================================
-- 002_rag.sql
-- Documentos + chunks vectorizados para RAG.
-- =====================================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_status') THEN
        CREATE TYPE public.document_status AS ENUM
            ('draft', 'processing', 'validated', 'archived', 'failed');
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    product_name text,
    country_iso char(2) REFERENCES public.countries(iso2) ON DELETE RESTRICT,
    language char(2) NOT NULL DEFAULT 'es',
    status public.document_status NOT NULL DEFAULT 'draft',
    source_filename text,
    content_sha256 text,
    markdown text,
    classification jsonb NOT NULL DEFAULT '{}'::jsonb,
    uploaded_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    validated_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    validated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_country
    ON public.documents (country_iso);

CREATE INDEX IF NOT EXISTS idx_documents_status
    ON public.documents (status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_content_sha
    ON public.documents (content_sha256)
    WHERE content_sha256 IS NOT NULL;

DROP TRIGGER IF EXISTS trg_documents_updated_at ON public.documents;
CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON public.documents
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------
-- Chunks vectorizados (text-embedding-3-small -> 1536 dims).
-- ---------------------------------------------------------------------
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

-- Indice ANN (HNSW con metrica cosine). Si la version de pgvector no
-- soporta HNSW (<0.5), cambiar a IVFFlat. El cost de creacion es alto
-- en tablas muy grandes pero arranca vacia.
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
    ON public.document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

COMMIT;
