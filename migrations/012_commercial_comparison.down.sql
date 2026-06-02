-- Rollback 012: comparador comercial.
-- Nota: el valor enum comparativo_comercial puede quedar huérfano.

BEGIN;

DROP TABLE IF EXISTS public.commercial_comparison_versions;
DROP TABLE IF EXISTS public.commercial_comparison_gaps;
DROP TABLE IF EXISTS public.commercial_comparison_cells;
DROP TABLE IF EXISTS public.commercial_comparison_rows;
DROP TABLE IF EXISTS public.commercial_comparison_columns;
DROP TABLE IF EXISTS public.commercial_comparison_sets;
DROP TABLE IF EXISTS public.competitors;

COMMIT;
