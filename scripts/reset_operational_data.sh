#!/usr/bin/env bash
# =====================================================================
# reset_operational_data.sh
#
# Ejecuta scripts/clean_test_data.sql (borrado masivo de datos operativos).
# Para preview y confirmación interactiva, usar ./scripts/clean_test_data.sh
#
# Uso (desde la raiz del repo):
#   ./scripts/reset_operational_data.sh
#
# Con Railway (inyecta DATABASE_URL):
#   railway run ./scripts/reset_operational_data.sh
#
# Requisitos: psql, DATABASE_URL; si falta, se intenta cargar ./.env.
# =====================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly SQL_FILE="${ROOT}/scripts/clean_test_data.sql"

log() {
  printf "[reset_operational_data] %s\n" "$*" >&2
}

if [[ ! -f "${SQL_FILE}" ]]; then
  log "ERROR: no existe ${SQL_FILE}"
  exit 2
fi

if [[ -z "${DATABASE_URL:-}" && -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  log "ERROR: DATABASE_URL no definida. Exportala o crea .env en la raiz del repo."
  exit 2
fi

cd "${ROOT}"

# Misma heuristica que railway_psql.sh para hostname interno de Railway.
conn="${DATABASE_URL}"
if [[ "${conn}" == *".railway.internal"* ]] && [[ -n "${DATABASE_PUBLIC_URL:-}" ]]; then
  log "Usando DATABASE_PUBLIC_URL (conexion fuera de la VPC Railway)."
  conn="${DATABASE_PUBLIC_URL}"
fi

exec psql "${conn}" -v ON_ERROR_STOP=1 -f "${SQL_FILE}"
