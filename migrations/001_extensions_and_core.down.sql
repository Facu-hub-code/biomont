-- =====================================================================
-- 001_extensions_and_core.down.sql
-- Rollback manual de la migracion 001.
-- ATENCION: borra tablas con datos. Confirmar antes de ejecutar.
-- =====================================================================

BEGIN;

DROP TRIGGER IF EXISTS trg_rtc_users_updated_at ON public.rtc_users;
DROP TRIGGER IF EXISTS trg_bo_users_updated_at ON public.bo_users;
DROP FUNCTION IF EXISTS public.set_updated_at();

DROP TABLE IF EXISTS public.rtc_user_countries;
DROP TABLE IF EXISTS public.rtc_users;
DROP TABLE IF EXISTS public.bo_audit_log;
DROP TABLE IF EXISTS public.bo_users;
DROP TYPE  IF EXISTS public.bo_role;
DROP TABLE IF EXISTS public.countries;

-- Las extensiones se mantienen porque pueden estar usadas por otras
-- migraciones / objetos.

COMMIT;
