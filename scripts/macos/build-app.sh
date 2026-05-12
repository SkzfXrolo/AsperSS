#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-ArgusScanner}"
SPEC_FILE="${SPEC_FILE:-ArgusScanner.spec}"

python -m pip install --upgrade pip pyinstaller
pyinstaller --clean --noconfirm --windowed --name "$APP_NAME" "$SPEC_FILE"
echo "OK: .app generado en dist/${APP_NAME}.app"
