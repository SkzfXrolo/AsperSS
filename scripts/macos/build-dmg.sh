#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-ArgusScanner}"
APP_PATH="${APP_PATH:-dist/${APP_NAME}.app}"
DMG_OUT="${DMG_OUT:-dist/${APP_NAME}.dmg}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: no existe $APP_PATH"
  exit 1
fi

if ! command -v create-dmg >/dev/null 2>&1; then
  echo "ERROR: instalar create-dmg (brew install create-dmg)"
  exit 1
fi

create-dmg --overwrite --dmg-title "$APP_NAME" "$DMG_OUT" "$APP_PATH"
echo "OK: DMG generado en $DMG_OUT"
