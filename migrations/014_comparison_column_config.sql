-- 014: Prioridad de columnas del comparador comercial (spec 016).

BEGIN;

ALTER TABLE public.commercial_comparison_columns
    ADD COLUMN IF NOT EXISTS display_tier smallint NOT NULL DEFAULT 3
        CHECK (display_tier BETWEEN 1 AND 4);

COMMENT ON COLUMN public.commercial_comparison_columns.display_tier IS
    '1=prioritaria (summary), 2=relevante, 3=normal, 4=solo detalle';

COMMIT;
