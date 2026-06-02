-- Rollback 011: motor de dosis.

BEGIN;

DELETE FROM public.agent_intent_config
WHERE intent_slug = 'dose_calculation';

DROP TABLE IF EXISTS public.product_dosing_versions;
DROP TABLE IF EXISTS public.product_dosing_gaps;
DROP TABLE IF EXISTS public.product_dosing_rules;
DROP TABLE IF EXISTS public.product_dosing_profiles;

COMMIT;
