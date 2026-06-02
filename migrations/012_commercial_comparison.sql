-- 012: Comparador comercial (columnas dinamicas por set, spec 012).

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum e
        JOIN pg_type t ON t.oid = e.enumtypid
        WHERE t.typname = 'document_kind' AND e.enumlabel = 'comparativo_comercial'
    ) THEN
        ALTER TYPE public.document_kind ADD VALUE 'comparativo_comercial';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.competitors (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    normalized_name text GENERATED ALWAYS AS (
        public.immutable_unaccent_lower(name)
    ) STORED,
    brand text,
    active_principles text,
    is_internal boolean NOT NULL DEFAULT false,
    linked_product_id uuid REFERENCES public.products(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (normalized_name)
);

CREATE INDEX IF NOT EXISTS idx_competitors_normalized_trgm
    ON public.competitors USING gin (normalized_name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS public.commercial_comparison_sets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    completeness_status text NOT NULL DEFAULT 'incomplete'
        CHECK (completeness_status IN ('complete', 'incomplete', 'not_applicable')),
    published_version integer NOT NULL DEFAULT 0,
    source_document_id uuid REFERENCES public.documents(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    UNIQUE (subject_product_id)
);

CREATE TABLE IF NOT EXISTS public.commercial_comparison_columns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    set_id uuid NOT NULL REFERENCES public.commercial_comparison_sets(id) ON DELETE CASCADE,
    column_key text NOT NULL,
    header_label text NOT NULL,
    sort_order integer NOT NULL DEFAULT 0,
    published_version integer NOT NULL DEFAULT 0,
    UNIQUE (set_id, column_key, published_version)
);

CREATE TABLE IF NOT EXISTS public.commercial_comparison_rows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    set_id uuid NOT NULL REFERENCES public.commercial_comparison_sets(id) ON DELETE CASCADE,
    display_name text NOT NULL,
    competitor_id uuid REFERENCES public.competitors(id) ON DELETE SET NULL,
    linked_product_id uuid REFERENCES public.products(id) ON DELETE SET NULL,
    is_subject boolean NOT NULL DEFAULT false,
    source_row jsonb,
    sort_order integer NOT NULL DEFAULT 0,
    published_version integer NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_commercial_comparison_rows_set
    ON public.commercial_comparison_rows (set_id, published_version);

CREATE TABLE IF NOT EXISTS public.commercial_comparison_cells (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    row_id uuid NOT NULL REFERENCES public.commercial_comparison_rows(id) ON DELETE CASCADE,
    column_key text NOT NULL,
    value_text text,
    published_version integer NOT NULL DEFAULT 0,
    UNIQUE (row_id, column_key, published_version)
);

CREATE TABLE IF NOT EXISTS public.commercial_comparison_gaps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    set_id uuid NOT NULL REFERENCES public.commercial_comparison_sets(id) ON DELETE CASCADE,
    gap_type text NOT NULL,
    severity text NOT NULL DEFAULT 'blocking'
        CHECK (severity IN ('blocking', 'warning')),
    details jsonb NOT NULL DEFAULT '{}',
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.commercial_comparison_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    set_id uuid NOT NULL REFERENCES public.commercial_comparison_sets(id) ON DELETE CASCADE,
    version integer NOT NULL,
    snapshot jsonb NOT NULL,
    published_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    published_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (set_id, version)
);

COMMIT;
