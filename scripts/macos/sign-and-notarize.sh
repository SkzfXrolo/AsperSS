#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${APP_PATH:-dist/ArgusScanner.app}"
DMG_PATH="${DMG_PATH:-dist/ArgusScanner.dmg}"
DEVELOPER_ID_APP="${DEVELOPER_ID_APP:-TBD_DEVELOPER_ID_APP}"
APPLE_ID="${APPLE_ID:-TBD_APPLE_ID}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-TBD_TEAM_ID}"
APPLE_APP_PASSWORD="${APPLE_APP_PASSWORD:-TBD_APP_PASSWORD}"

codesign --deep --force --verify --verbose --timestamp \
  --sign "$DEVELOPER_ID_APP" "$APP_PATH"

if [[ -f "$DMG_PATH" ]]; then
  codesign --force --verify --verbose --timestamp \
    --sign "$DEVELOPER_ID_APP" "$DMG_PATH"
fi

xcrun notarytool submit "$DMG_PATH" \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_APP_PASSWORD" \
  --wait

xcrun stapler staple "$APP_PATH"
[[ -f "$DMG_PATH" ]] && xcrun stapler staple "$DMG_PATH"
echo "OK: firma y notarizacion finalizadas."
