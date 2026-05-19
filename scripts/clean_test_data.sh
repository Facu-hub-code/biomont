#!/usr/bin/env bash
# =====================================================================
# clean_test_data.sh
#
# Limpia de la base datos de prueba: chats, tickets, decisiones del agente,
# documentos (RAG) y productos. Muestra conteos y pide confirmación.
#
# Uso (desde la raíz del repo):
#   ./scripts/clean_test_data.sh              # preview + confirmación interactiva
#   ./scripts/clean_test_data.sh --yes        # sin confirmación
#   ./scripts/clean_test_data.sh --dry-run    # solo muestra conteos
#
# Con Railway:
#   railway run ./scripts/clean_test_data.sh
#
# Requisitos: psql, DATABASE_URL (o .env en la raíz del repo).
# =====================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly SQL_FILE="${ROOT}/scripts/clean_test_data.sql"

DRY_RUN=false
ASSUME_YES=false

log() {
  printf "[clean_test_data] %s\n" "$*" >&2
}

usage() {
  sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --yes|-y)
      ASSUME_YES=true
      shift
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      log "ERROR: opción desconocida: $1"
      usage 1
      ;;
  esac
done

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
  log "ERROR: DATABASE_URL no definida. Exportala o crea .env en la raíz del repo."
  exit 2
fi

conn="${DATABASE_URL}"
if [[ "${conn}" == *".railway.internal"* ]] && [[ -n "${DATABASE_PUBLIC_URL:-}" ]]; then
  log "Usando DATABASE_PUBLIC_URL (conexión fuera de la VPC Railway)."
  conn="${DATABASE_PUBLIC_URL}"
fi

readonly COUNTS_SQL="
SELECT 'conversations (chats)' AS entidad, count(*)::text AS filas FROM public.conversations
UNION ALL SELECT 'messages', count(*)::text FROM public.messages
UNION ALL SELECT 'conversation_state', count(*)::text FROM public.conversation_state
UNION ALL SELECT 'agent_decisions', count(*)::text FROM public.agent_decisions
UNION ALL SELECT 'tickets', count(*)::text FROM public.tickets
UNION ALL SELECT 'documents', count(*)::text FROM public.documents
UNION ALL SELECT 'document_chunks (legacy)', count(*)::text FROM public.document_chunks
UNION ALL SELECT 'document_sections', count(*)::text FROM public.document_sections
UNION ALL SELECT 'knowledge_chunks', count(*)::text FROM public.knowledge_chunks
UNION ALL SELECT 'faq_entries', count(*)::text FROM public.faq_entries
UNION ALL SELECT 'document_products', count(*)::text FROM public.document_products
UNION ALL SELECT 'products', count(*)::text FROM public.products
UNION ALL SELECT 'product_aliases', count(*)::text FROM public.product_aliases
UNION ALL SELECT 'bo_audit_log', count(*)::text FROM public.bo_audit_log
ORDER BY 1;
"

log "Estado actual de datos operativos:"
psql "${conn}" -v ON_ERROR_STOP=1 -c "${COUNTS_SQL}"

if [[ "${DRY_RUN}" == true ]]; then
  log "Modo --dry-run: no se borró nada."
  exit 0
fi

log ""
log "Se borrarán: chats, tickets, decisiones del agente, documentos (RAG) y productos."
log "Se conservan: usuarios backoffice/RTC, países y system_prompts."
log ""

cd "${ROOT}"

if [[ "${ASSUME_YES}" != true ]]; then
  read -r -p "¿Continuar? Escribí 'si' para confirmar: " answer
  if [[ "${answer}" != "si" ]]; then
    log "Cancelado."
    exit 0
  fi
fi

psql "${conn}" -v ON_ERROR_STOP=1 -f "${SQL_FILE}"

log "Limpieza completada."
log "Estado posterior:"
psql "${conn}" -v ON_ERROR_STOP=1 -c "${COUNTS_SQL}"
