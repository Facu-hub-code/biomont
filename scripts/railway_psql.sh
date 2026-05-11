#!/usr/bin/env bash
# Ejecuta psql contra el Postgres de Railway cuando usas `railway run` en tu equipo.
# `railway run psql ...` falla porque PGHOST apunta a *.railway.internal (no resuelve fuera de la VPC).
#
# Uso:
#   railway run ./scripts/railway_psql.sh -f scripts/seed_dev.sql
#   railway run ./scripts/railway_psql.sh -c '\dt'
#
# Requiere variables inyectadas por Railway (servicio Postgres enlazado o referencias).

set -euo pipefail

log() {
    printf "[railway_psql] %s\n" "$*" >&2
}

conn="${DATABASE_URL:-}"
if [[ -z "${conn}" ]]; then
    log "ERROR: DATABASE_URL no esta seteada. Ejecutar con: railway run $0 ..."
    exit 2
fi

if [[ "${conn}" == *".railway.internal"* ]] && [[ -n "${DATABASE_PUBLIC_URL:-}" ]]; then
    log "Usando DATABASE_PUBLIC_URL (conexion local / fuera de la VPC Railway)."
    conn="${DATABASE_PUBLIC_URL}"
fi

exec psql "${conn}" "$@"
