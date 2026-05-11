-- =====================================================================
-- 001_extensions_and_core.sql
-- Extensiones requeridas + catalogo de paises + RBAC backoffice + RTCs.
-- =====================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------
-- Catalogo de paises (codigo ISO 3166-1 alpha-2).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.countries (
    iso2 char(2) PRIMARY KEY,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Usuarios del backoffice (autenticacion + RBAC simple).
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bo_role') THEN
        CREATE TYPE public.bo_role AS ENUM ('admin', 'scientist', 'viewer');
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.bo_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    name text NOT NULL,
    role public.bo_role NOT NULL DEFAULT 'viewer',
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bo_users_email
    ON public.bo_users (lower(email));

-- ---------------------------------------------------------------------
-- Audit log generico del backoffice.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.bo_audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    entity text NOT NULL,
    entity_id uuid,
    action text NOT NULL,
    before jsonb,
    after jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bo_audit_log_entity
    ON public.bo_audit_log (entity, entity_id, created_at DESC);

-- ---------------------------------------------------------------------
-- RTCs habilitados a interactuar via WhatsApp.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.rtc_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_e164 text NOT NULL UNIQUE,
    name text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    created_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rtc_users_phone
    ON public.rtc_users (phone_e164);

CREATE TABLE IF NOT EXISTS public.rtc_user_countries (
    rtc_user_id uuid NOT NULL REFERENCES public.rtc_users(id) ON DELETE CASCADE,
    country_iso char(2) NOT NULL REFERENCES public.countries(iso2) ON DELETE RESTRICT,
    PRIMARY KEY (rtc_user_id, country_iso)
);

-- ---------------------------------------------------------------------
-- Helper: trigger para mantener updated_at.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_bo_users_updated_at ON public.bo_users;
CREATE TRIGGER trg_bo_users_updated_at
    BEFORE UPDATE ON public.bo_users
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS trg_rtc_users_updated_at ON public.rtc_users;
CREATE TRIGGER trg_rtc_users_updated_at
    BEFORE UPDATE ON public.rtc_users
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------
-- Seed minimo del catalogo de paises (alcance regional de Biomont).
-- ---------------------------------------------------------------------
INSERT INTO public.countries (iso2, name) VALUES
    ('PE', 'Peru'),
    ('BO', 'Bolivia'),
    ('EC', 'Ecuador'),
    ('CO', 'Colombia'),
    ('CL', 'Chile'),
    ('MX', 'Mexico'),
    ('AR', 'Argentina')
ON CONFLICT (iso2) DO NOTHING;

COMMIT;
