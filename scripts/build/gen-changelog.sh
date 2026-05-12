#!/usr/bin/env bash
set -euo pipefail

FROM_REF="${1:-}"
TO_REF="${2:-HEAD}"
OUTPUT_FILE="${3:-CHANGELOG.md}"

if [[ -z "$FROM_REF" ]]; then
  LAST_TAG="$(git describe --tags --abbrev=0 2>/dev/null || true)"
  FROM_REF="${LAST_TAG:-HEAD~50}"
fi

{
  echo "# Changelog"
  echo
  echo "Generado automaticamente desde commits."
  echo
  echo "## Cambios ($FROM_REF..$TO_REF)"
  git log --pretty=format:'- %s (%h)' "$FROM_REF..$TO_REF"
  echo
} > "$OUTPUT_FILE"

echo "OK: changelog generado en $OUTPUT_FILE"
