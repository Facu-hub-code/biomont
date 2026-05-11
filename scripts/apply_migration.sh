#!/usr/bin/env bash
# Aplica una migracion SQL versionada contra el Postgres remoto (Railway).
#
# Uso:
#   ./scripts/apply_migration.sh 001
#   ./scripts/apply_migration.sh 002 --down   # aplica la version .down.sql
#
# Variables requeridas:
#   DATABASE_URL  (alternativa: usar `railway run` para inyectarla)
#
# Convenciones:
#   migrations/NNN_*.sql       -> migracion "up"
#   migrations/NNN_*.down.sql  -> rollback manual asociado

set -euo pipefail

readonly REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
readonly MIGRATIONS_DIR="${REPO_ROOT}/migrations"

log() {
    printf "[apply_migration] %s\n" "$*" >&2
}

usage() {
    log "Uso: $0 <numero-migracion> [--down]"
    log "Ejemplo: $0 001"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

readonly VERSION="$1"
readonly DIRECTION="${2:-up}"

if [[ -z "${DATABASE_URL:-}" ]]; then
    log "ERROR: DATABASE_URL no esta seteada."
    log "Tip: ejecutar con 'railway run ./scripts/apply_migration.sh ${VERSION}'."
    exit 2
fi

# `railway run` ejecuta en tu equipo: el host *.railway.internal no resuelve fuera
# de la red de Railway. Si existe URL publica del plugin Postgres, usarla.
if [[ "${DATABASE_URL}" == *".railway.internal"* ]] && [[ -n "${DATABASE_PUBLIC_URL:-}" ]]; then
    log "Usando DATABASE_PUBLIC_URL (conexion local / fuera de la VPC Railway)."
    DATABASE_URL="${DATABASE_PUBLIC_URL}"
fi

case "${DIRECTION}" in
    up|--up)
        pattern="${VERSION}_*.sql"
        ;;
    down|--down)
        pattern="${VERSION}_*.down.sql"
        ;;
    *)
        log "ERROR: direccion invalida '${DIRECTION}'. Usar 'up' o '--down'."
        exit 1
        ;;
esac

# shellcheck disable=SC2086
matches=( ${MIGRATIONS_DIR}/${pattern} )
filtered=()
for f in "${matches[@]}"; do
    [[ -f "${f}" ]] || continue
    if [[ "${DIRECTION}" == "up" || "${DIRECTION}" == "--up" ]]; then
        if [[ "${f}" == *.down.sql ]]; then
            continue
        fi
    fi
    filtered+=( "${f}" )
done

if [[ ${#filtered[@]} -eq 0 ]]; then
    log "ERROR: no se encontro migracion para '${VERSION}' (${DIRECTION})."
    exit 3
fi

if [[ ${#filtered[@]} -gt 1 ]]; then
    log "ERROR: mas de un archivo coincide con '${VERSION}' (${DIRECTION}):"
    printf '  %s\n' "${filtered[@]}" >&2
    exit 4
fi

readonly MIGRATION_FILE="${filtered[0]}"

log "Aplicando: ${MIGRATION_FILE}"
log "Contra: $(echo "${DATABASE_URL}" | sed -E 's#(://[^:]+:)[^@]+(@)#\1****\2#')"

if ! command -v psql >/dev/null 2>&1; then
    log "ERROR: psql no esta instalado en el PATH."
    exit 5
fi

psql "${DATABASE_URL}" \
    --single-transaction \
    --set ON_ERROR_STOP=on \
    --file "${MIGRATION_FILE}"

log "OK: migracion aplicada."
