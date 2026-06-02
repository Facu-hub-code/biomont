-- Restaura hints cortos de 011 (aproximado).
BEGIN;

UPDATE public.agent_intent_config AS ic
SET classifier_hint = 'calcular dosis, cuantos ml, que tableta, que presentacion, perro de X kg, vaca de X kg, ternero, volumen a administrar, cuantas tabletas segun peso.'
FROM public.agent_config_versions v
WHERE v.is_active = true
  AND ic.config_version_id = v.id
  AND ic.intent_slug = 'dose_calculation';

UPDATE public.agent_intent_config AS ic
SET classifier_hint = 'dosis, cuanto administrar, presentaciones, via o modo de administracion, indicacion o indicaciones terapeuticas/de uso.'
FROM public.agent_config_versions v
WHERE v.is_active = true
  AND ic.config_version_id = v.id
  AND ic.intent_slug = 'dosage_question';

COMMIT;
