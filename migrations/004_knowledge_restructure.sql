-- =====================================================================
-- 004_knowledge_restructure.sql
-- Productos + aliases + secciones + knowledge_chunks (hibrido vec+bm25)
-- + faq_entries + conversation_state + extensiones de documents.
-- Implementa spec docs/specs/003-langgraph-hybrid-rag-and-knowledge-restructure.md
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ---------------------------------------------------------------------
-- Enum: tipo de documento (ficha_tecnica, bitacora, balotario).
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'document_kind') THEN
        CREATE TYPE public.document_kind AS ENUM
            ('ficha_tecnica', 'bitacora', 'balotario');
    END IF;
END;
$$;

-- ---------------------------------------------------------------------
-- Helper inmutable para indices/generated columns sobre texto normalizado.
-- ---------------------------------------------------------------------
-- unaccent es STABLE por default, no IMMUTABLE, lo que impide usarla en
-- generated columns o indices funcionales. Envolvemos en una wrapper
-- marcada IMMUTABLE (patron canonico). Si el diccionario unaccent cambia,
-- hay que reindexar manualmente.
CREATE OR REPLACE FUNCTION public.immutable_unaccent_lower(value text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT lower(public.unaccent('public.unaccent'::regdictionary, value));
$$;

-- ---------------------------------------------------------------------
-- products: entidad de primera clase. Reemplaza el string libre
-- documents.product_name. UNIQUE por (lower(name), COALESCE(country_iso, 'XX'))
-- para tratar NULL como "global".
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.products (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    brand text NOT NULL DEFAULT 'Biomont',
    duration_type text,
    description text,
    country_iso char(2) REFERENCES public.countries(iso2) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_products_name_country
    ON public.products (lower(name), COALESCE(country_iso, 'XX'::char(2)));

DROP TRIGGER IF EXISTS trg_products_updated_at ON public.products;
CREATE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON public.products
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------
-- product_aliases: variantes textuales (colores, "el de 3 meses", etc).
-- normalized_alias se genera con immutable_unaccent_lower para indice
-- trigram GIN.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.product_aliases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    alias text NOT NULL,
    normalized_alias text GENERATED ALWAYS AS
        (public.immutable_unaccent_lower(alias)) STORED,
    source text NOT NULL DEFAULT 'manual'
        CHECK (source IN ('name', 'manual', 'bootstrap')),
    confidence numeric(3,2) NOT NULL DEFAULT 1.0,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (product_id, normalized_alias)
);

CREATE INDEX IF NOT EXISTS idx_product_aliases_norm_trgm
    ON public.product_aliases USING gin (normalized_alias gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_product_aliases_product
    ON public.product_aliases (product_id);

-- ---------------------------------------------------------------------
-- Extender documents con kind + product_id (FK opcional).
-- Backfill: kind='bitacora' (mas frecuente), product_id NULL.
-- El bootstrap_products.py reasocia product_id por match exacto.
-- ---------------------------------------------------------------------
ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS kind public.document_kind NOT NULL DEFAULT 'bitacora';

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS product_id uuid
        REFERENCES public.products(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_documents_product
    ON public.documents (product_id);

CREATE INDEX IF NOT EXISTS idx_documents_kind
    ON public.documents (kind);

-- ---------------------------------------------------------------------
-- document_sections: estructura jerarquica del documento.
-- Permite agrupar chunks por seccion clinica.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.document_sections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    section_index integer NOT NULL,
    parent_section_id uuid REFERENCES public.document_sections(id) ON DELETE SET NULL,
    section_number text,
    section_title text,
    section_kind text,
    page_start integer,
    page_end integer,
    raw_text text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, section_index)
);

CREATE INDEX IF NOT EXISTS idx_document_sections_document
    ON public.document_sections (document_id, section_index);

-- ---------------------------------------------------------------------
-- knowledge_chunks: reemplazo enriquecido de document_chunks.
-- Mantenemos document_chunks intacto durante la transicion (feature flag).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.knowledge_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    section_id uuid REFERENCES public.document_sections(id) ON DELETE SET NULL,
    product_id uuid REFERENCES public.products(id) ON DELETE SET NULL,
    kind public.document_kind NOT NULL,
    chunk_index integer NOT NULL,
    section_type text,
    subsection_type text,
    topic text,
    content text NOT NULL,
    token_count integer NOT NULL DEFAULT 0,
    contains_table boolean NOT NULL DEFAULT false,
    contains_dose boolean NOT NULL DEFAULT false,
    species text[] NOT NULL DEFAULT '{}',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS
        (to_tsvector('spanish', coalesce(content, ''))) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document
    ON public.knowledge_chunks (document_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_product_kind
    ON public.knowledge_chunks (product_id, kind);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_kind_section
    ON public.knowledge_chunks (kind, section_type);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_tsv
    ON public.knowledge_chunks USING gin (tsv);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding_hnsw
    ON public.knowledge_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ---------------------------------------------------------------------
-- faq_entries: balotario indexado para retrieval directo.
-- ---------------------------------------------------------------------
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

-- ---------------------------------------------------------------------
-- conversation_state: memoria 1:1 con conversations.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.conversation_state (
    conversation_id uuid PRIMARY KEY
        REFERENCES public.conversations(id) ON DELETE CASCADE,
    current_product_id uuid REFERENCES public.products(id) ON DELETE SET NULL,
    current_topic text,
    current_species text,
    last_intent text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversation_state_product
    ON public.conversation_state (current_product_id);

DROP TRIGGER IF EXISTS trg_conversation_state_updated_at ON public.conversation_state;
CREATE TRIGGER trg_conversation_state_updated_at
    BEFORE UPDATE ON public.conversation_state
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------
-- agent_decisions: campo de trazabilidad del grafo (opcional, default []).
-- ---------------------------------------------------------------------
ALTER TABLE public.agent_decisions
    ADD COLUMN IF NOT EXISTS graph_trace jsonb NOT NULL DEFAULT '[]'::jsonb;

COMMIT;
