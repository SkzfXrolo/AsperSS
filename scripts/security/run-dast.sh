#!/usr/bin/env bash
set -euo pipefail

TARGET_URL="${1:-}"
if [ -z "${TARGET_URL}" ]; then
  echo "Usage: $0 <staging-url>"
  exit 1
fi

OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/security-artifacts/dast"
mkdir -p "${OUT_DIR}"

echo "[dast] target: ${TARGET_URL}"
if command -v nuclei >/dev/null 2>&1; then
  nuclei -u "${TARGET_URL}" -severity critical,high,medium -json -o "${OUT_DIR}/nuclei.json" || true
  echo "[dast] report: ${OUT_DIR}/nuclei.json"
else
  echo "[dast] nuclei not installed"
fi
