-- =====================================================================
-- 006_product_document_links.down.sql
-- Rollback spec 006. documents.product_id conserva el ultimo primario.
-- =====================================================================

BEGIN;

DROP INDEX IF EXISTS public.idx_document_products_document;
DROP INDEX IF EXISTS public.idx_document_products_product;
DROP INDEX IF EXISTS public.uq_document_products_one_primary;
DROP TABLE IF EXISTS public.document_products;

COMMIT;
