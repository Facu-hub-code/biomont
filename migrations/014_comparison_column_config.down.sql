-- 014 down: quitar display_tier del comparador.

BEGIN;

ALTER TABLE public.commercial_comparison_columns
    DROP COLUMN IF EXISTS display_tier;

COMMIT;
