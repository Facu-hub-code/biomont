#!/usr/bin/env bash
# =====================================================================
# seed_admin.sh
#
# Crea o actualiza el admin del backoffice con un hash argon2id real,
# sin hardcodear secrets en archivos versionados.
#
# Uso:
#   ./scripts/seed_admin.sh <email> <password>
#   railway run ./scripts/seed_admin.sh admin@example.com 'miSecreto123'
#
# Requisitos:
#   - DATABASE_URL exportada (o ejecutar con `railway run`).
#   - `psql` en el PATH.
#   - Python 3 con `argon2-cffi` instalado:
#       pip install argon2-cffi
# =====================================================================

set -euo pipefail

log() {
    printf "[seed_admin] %s\n" "$*" >&2
}

if [[ $# -lt 2 ]]; then
    log "Uso: $0 <email> <password>"
    log "Ejemplo: $0 admin@example.com 'unaPasswordFuerte'"
    exit 1
fi

readonly EMAIL="$1"
readonly PASSWORD="$2"

if [[ -z "${DATABASE_URL:-}" ]]; then
    log "ERROR: DATABASE_URL no esta seteada."
    log "Tip: ejecutar con 'railway run ./scripts/seed_admin.sh ...'."
    exit 2
fi

# `railway run` en local: *.railway.internal no resuelve fuera de la VPC.
if [[ "${DATABASE_URL}" == *".railway.internal"* ]] && [[ -n "${DATABASE_PUBLIC_URL:-}" ]]; then
    log "Usando DATABASE_PUBLIC_URL (conexion local / fuera de la VPC Railway)."
    DATABASE_URL="${DATABASE_PUBLIC_URL}"
fi

if ! command -v psql >/dev/null 2>&1; then
    log "ERROR: psql no esta instalado en el PATH."
    exit 3
fi

if ! command -v python3 >/dev/null 2>&1; then
    log "ERROR: python3 no esta instalado."
    exit 4
fi

# Validacion basica del email (no exhaustiva, pero atrapa los TLDs
# reservados que pydantic EmailStr rechaza, tipo `.local`).
if [[ "${EMAIL}" =~ \.(local|test|invalid|example)$ ]] \
   && [[ ! "${EMAIL}" =~ @example\.com$ ]]; then
    log "ADVERTENCIA: el TLD '${EMAIL##*.}' es reservado."
    log "Pydantic EmailStr lo rechaza. Usar un dominio publico real."
fi

# Generamos el hash via Python (argon2-cffi) y lo capturamos en una var.
# Pasamos la password por stdin para no exponerla en argv.
HASH="$(
    PASSWORD_INPUT="${PASSWORD}" python3 - <<'PY'
import os
import sys

try:
    from argon2 import PasswordHasher
except ImportError:
    sys.stderr.write(
        "argon2-cffi no esta instalado. Ejecuta: pip install argon2-cffi\n"
    )
    sys.exit(10)

print(PasswordHasher().hash(os.environ["PASSWORD_INPUT"]))
PY
)"

log "Hash generado. Insertando admin en bo_users..."

psql "${DATABASE_URL}" \
    --single-transaction \
    --set ON_ERROR_STOP=on \
    --quiet \
    --variable=email="${EMAIL}" \
    --variable=password_hash="${HASH}" <<'SQL'
INSERT INTO public.bo_users (email, password_hash, name, role, is_active)
VALUES (:'email', :'password_hash', 'Admin Biomont', 'admin', true)
ON CONFLICT (email) DO UPDATE
SET password_hash = EXCLUDED.password_hash,
    is_active = true;
SQL

log "OK: admin '${EMAIL}' listo. Cambia la password apenas inicies sesion."
