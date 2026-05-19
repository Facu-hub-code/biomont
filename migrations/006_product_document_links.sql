-- =====================================================================
-- 006_product_document_links.sql
-- Relacion N:M products <-> documents (spec 006).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.document_products (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
    product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    UNIQUE (document_id, product_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_document_products_one_primary
    ON public.document_products (document_id)
    WHERE is_primary;

CREATE INDEX IF NOT EXISTS idx_document_products_product
    ON public.document_products (product_id);

CREATE INDEX IF NOT EXISTS idx_document_products_document
    ON public.document_products (document_id);

INSERT INTO public.document_products (document_id, product_id, is_primary)
SELECT d.id, d.product_id, true
FROM public.documents d
WHERE d.product_id IS NOT NULL
ON CONFLICT (document_id, product_id) DO NOTHING;

COMMIT;
