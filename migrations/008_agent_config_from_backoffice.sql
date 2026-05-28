-- 008: Configuracion versionada del agente (top-k, intents, kinds) editable desde backoffice.

BEGIN;

CREATE TABLE IF NOT EXISTS public.agent_config_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    version integer NOT NULL UNIQUE,
    is_active boolean NOT NULL DEFAULT false,
    top_k integer NOT NULL DEFAULT 6
        CHECK (top_k >= 1 AND top_k <= 20),
    candidate_k integer NOT NULL DEFAULT 25
        CHECK (candidate_k >= 5 AND candidate_k <= 100),
    full_corpus_for_all_intents boolean NOT NULL DEFAULT false,
    classifier_preamble text,
    created_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (top_k <= candidate_k)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_config_versions_active
    ON public.agent_config_versions ((is_active))
    WHERE is_active = true;

CREATE TABLE IF NOT EXISTS public.agent_intent_config (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    config_version_id uuid NOT NULL
        REFERENCES public.agent_config_versions(id) ON DELETE CASCADE,
    intent_slug text NOT NULL,
    display_label text NOT NULL,
    classifier_hint text NOT NULL,
    document_kinds text[] NOT NULL DEFAULT '{}',
    sort_order integer NOT NULL DEFAULT 0,
    is_enabled boolean NOT NULL DEFAULT true,
    UNIQUE (config_version_id, intent_slug)
);

CREATE INDEX IF NOT EXISTS idx_agent_intent_config_version_order
    ON public.agent_intent_config (config_version_id, sort_order);

-- Version inicial activa (spec 008).
INSERT INTO public.agent_config_versions (
    version, is_active, top_k, candidate_k, full_corpus_for_all_intents, classifier_preamble
)
VALUES (
    1,
    true,
    6,
    25,
    false,
    'Sos un clasificador de intencion para un agente veterinario de productos (fichas tecnicas, bitacoras, balotarios).'
)
ON CONFLICT (version) DO NOTHING;

INSERT INTO public.agent_intent_config (
    config_version_id, intent_slug, display_label, classifier_hint, document_kinds, sort_order, is_enabled
)
SELECT
    v.id,
    i.intent_slug,
    i.display_label,
    i.classifier_hint,
    i.document_kinds,
    i.sort_order,
    true
FROM public.agent_config_versions v
CROSS JOIN (
    VALUES
        (
            'dosage_question',
            'Dosis y uso',
            'dosis, cuanto administrar, presentaciones, via o modo de administracion, frecuencia, duracion del tratamiento, uso operativo del producto, indicacion o indicaciones terapeuticas/de uso, para que sirve, en que casos o enfermedades se utiliza, si aplica en una especie o edad (cuando el foco no es solo riesgo/seguridad).',
            ARRAY['bitacora', 'ficha_tecnica', 'balotario']::text[],
            10
        ),
        (
            'clinical_protocol',
            'Protocolo clinico',
            'protocolo terapeutico nombrado o esquema de tratamiento (ej. DAPP, desparasitacion en etapas), pasos de un protocolo clinico.',
            ARRAY['bitacora', 'balotario']::text[],
            20
        ),
        (
            'comparison_with_competitor',
            'Comparacion',
            'comparacion con otro producto (Bravecto, Atrevia, etc).',
            ARRAY['bitacora']::text[],
            30
        ),
        (
            'safety_question',
            'Seguridad',
            'efectos adversos, reacciones adversas/eventos adversos, tolerancia, contraindicaciones, toxicidad, sobredosis, interacciones, seguridad en gestacion/lactancia, uso en hepaticos/renales, edades minimas, collies/blancos/MDR1 cuando el foco sea riesgo clinico para el paciente.',
            ARRAY['ficha_tecnica', 'bitacora', 'balotario']::text[],
            40
        ),
        (
            'chitchat',
            'Saludo',
            'saludo o conversacion casual sin consulta clinica.',
            '{}'::text[],
            50
        ),
        (
            'out_of_scope',
            'Fuera de dominio',
            'SOLO temas ajenos al dominio veterinario-farmaceutico del agente (politica, geografia, recetas de medicina humana, chistes, etc.).',
            '{}'::text[],
            60
        )
) AS i(intent_slug, display_label, classifier_hint, document_kinds, sort_order)
WHERE v.version = 1
ON CONFLICT (config_version_id, intent_slug) DO NOTHING;

COMMIT;
