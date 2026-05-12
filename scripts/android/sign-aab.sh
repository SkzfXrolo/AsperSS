#!/usr/bin/env bash
set -euo pipefail

AAB_PATH="${AAB_PATH:-mobile/argus_android/app/build/outputs/bundle/release/app-release.aab}"
KEYSTORE_PATH="${KEYSTORE_PATH:-TBD_KEYSTORE}"
KEY_ALIAS="${KEY_ALIAS:-TBD_ALIAS}"

jarsigner -keystore "$KEYSTORE_PATH" "$AAB_PATH" "$KEY_ALIAS"
echo "OK: AAB firmado."
