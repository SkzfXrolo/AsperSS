#!/usr/bin/env bash
set -euo pipefail

PACKAGE_NAME="${PACKAGE_NAME:-com.argusprojects.app}"
AAB_PATH="${AAB_PATH:-mobile/argus_android/app/build/outputs/bundle/release/app-release.aab}"

echo "REVIEW: integrar Google Play Developer API para $PACKAGE_NAME"
echo "AAB objetivo: $AAB_PATH"
