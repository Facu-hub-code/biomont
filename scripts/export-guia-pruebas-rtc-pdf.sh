#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HTML="$ROOT/docs/export/guia-pruebas-rtc.html"
PDF="$ROOT/docs/guia-pruebas-rtc.pdf"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if [[ ! -f "$HTML" ]]; then
  echo "No se encontró $HTML" >&2
  exit 1
fi

if [[ ! -x "$CHROME" ]]; then
  echo "Google Chrome no está instalado en la ruta esperada." >&2
  exit 1
fi

"$CHROME" \
  --headless=new \
  --disable-gpu \
  --no-sandbox \
  --run-all-compositor-stages-before-draw \
  --virtual-time-budget=15000 \
  --print-to-pdf="$PDF" \
  "file://$HTML"

echo "PDF generado: $PDF"
