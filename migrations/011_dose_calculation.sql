-- 011: Motor de calculo de dosis (spec 011).
-- Perfiles multi-especie, reglas formula/rango, gaps y versionado.

BEGIN;

CREATE TABLE IF NOT EXISTS public.product_dosing_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    species text NOT NULL,
    supports_dose_calculation boolean NOT NULL DEFAULT false,
    min_age_weeks integer,
    max_age_weeks integer,
    min_weight_kg numeric(8, 2),
    max_weight_kg numeric(8, 2),
    completeness_status text NOT NULL DEFAULT 'incomplete'
        CHECK (completeness_status IN ('complete', 'incomplete', 'not_applicable')),
    completeness_notes text,
    published_version integer NOT NULL DEFAULT 0,
    source_document_id uuid REFERENCES public.documents(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    UNIQUE (product_id, species)
);

CREATE INDEX IF NOT EXISTS idx_product_dosing_profiles_product
    ON public.product_dosing_profiles (product_id);

CREATE TABLE IF NOT EXISTS public.product_dosing_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid NOT NULL REFERENCES public.product_dosing_profiles(id) ON DELETE CASCADE,
    rule_type text NOT NULL CHECK (rule_type IN ('formula', 'weight_band')),
    label text,
    formula_numerator numeric(12, 4),
    formula_denominator numeric(12, 4) DEFAULT 1,
    formula_per_kg boolean NOT NULL DEFAULT true,
    weight_min_kg numeric(8, 2),
    weight_max_kg numeric(8, 2),
    weight_min_inclusive boolean NOT NULL DEFAULT true,
    weight_max_inclusive boolean NOT NULL DEFAULT true,
    output_value numeric(12, 4),
    output_unit text NOT NULL DEFAULT 'mg'
        CHECK (output_unit IN ('ml', 'mg', 'tablets', 'doses')),
    min_output numeric(12, 4),
    max_output numeric(12, 4),
    sort_order integer NOT NULL DEFAULT 0,
    is_active boolean NOT NULL DEFAULT true,
    published_version integer NOT NULL DEFAULT 0,
    CHECK (
        (rule_type = 'formula' AND formula_numerator IS NOT NULL)
        OR (rule_type = 'weight_band' AND weight_min_kg IS NOT NULL AND weight_max_kg IS NOT NULL)
    ),
    CHECK (weight_min_kg IS NULL OR weight_max_kg IS NULL OR weight_min_kg < weight_max_kg)
);

CREATE INDEX IF NOT EXISTS idx_product_dosing_rules_profile
    ON public.product_dosing_rules (profile_id, published_version, sort_order);

CREATE TABLE IF NOT EXISTS public.product_dosing_gaps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES public.product_dosing_profiles(id) ON DELETE CASCADE,
    gap_type text NOT NULL,
    severity text NOT NULL DEFAULT 'blocking'
        CHECK (severity IN ('blocking', 'warning')),
    details jsonb NOT NULL DEFAULT '{}',
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_dosing_gaps_product_open
    ON public.product_dosing_gaps (product_id)
    WHERE resolved_at IS NULL;

CREATE TABLE IF NOT EXISTS public.product_dosing_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    profile_id uuid NOT NULL REFERENCES public.product_dosing_profiles(id) ON DELETE CASCADE,
    version integer NOT NULL,
    snapshot jsonb NOT NULL,
    published_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    published_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (profile_id, version)
);

-- Intent dose_calculation en config activa.
INSERT INTO public.agent_intent_config (
    config_version_id, intent_slug, display_label, classifier_hint,
    document_kinds, sort_order, is_enabled
)
SELECT
    v.id,
    'dose_calculation',
    'Calculo de dosis',
    'Calculo por peso: que dosis le doy, que tableta/presentacion, cuantos ml, perro/vaca de X kg. No usar para indicaciones generales ni gestacion.',
    ARRAY[]::text[],
    5,
    true
FROM public.agent_config_versions v
WHERE v.is_active = true
ON CONFLICT (config_version_id, intent_slug) DO UPDATE SET
    display_label = EXCLUDED.display_label,
    classifier_hint = EXCLUDED.classifier_hint,
    sort_order = EXCLUDED.sort_order,
    is_enabled = EXCLUDED.is_enabled;

COMMIT;
