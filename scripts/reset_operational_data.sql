-- =====================================================================
-- reset_operational_data.sql
--
-- Alias del borrado definido en clean_test_data.sql (mismo contenido).
-- Preferir: ./scripts/clean_test_data.sh (preview + confirmación).
--
-- Uso:
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/reset_operational_data.sql
-- =====================================================================

\ir clean_test_data.sql
