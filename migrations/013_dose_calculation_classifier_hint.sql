-- Mejora hints del clasificador para enrutar preguntas naturales de calculo de dosis.
BEGIN;

UPDATE public.agent_intent_config AS ic
SET classifier_hint = $hint$
Elegi esta etiqueta cuando el usuario pide CALCULAR que presentacion, tableta, ml o mg usar segun el PESO del animal (ej. perro de 25 kg, vaca de 450 kg). Incluye frases como: que dosis le doy, cuanta dosis, que tableta, calcular dosis, cuantos ml, que presentacion/comprimido. NO uses esta etiqueta para indicaciones generales, posologia en gestacion, administracion con/sin alimento, o contraindicaciones (usa dosage_question o safety_question).
$hint$
FROM public.agent_config_versions v
WHERE v.is_active = true
  AND ic.config_version_id = v.id
  AND ic.intent_slug = 'dose_calculation';

UPDATE public.agent_intent_config AS ic
SET classifier_hint = $hint$
Dosis o posologia INFORMATIVA en texto (indicaciones, modo de uso, cuando no conviene, administracion general) SIN pedir calculo por peso del animal. Si hay peso en kg y pregunta que darle/le doy/que tableta -> dose_calculation, no esta etiqueta.
$hint$
FROM public.agent_config_versions v
WHERE v.is_active = true
  AND ic.config_version_id = v.id
  AND ic.intent_slug = 'dosage_question';

COMMIT;
