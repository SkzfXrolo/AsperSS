#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-mobile/argus_android}"
TARGET_SDK="${TARGET_SDK:-34}"

echo "Build Android App Bundle (targetSdk=$TARGET_SDK)"
cd "$PROJECT_DIR"

if [[ ! -f "gradlew" ]]; then
  echo "ERROR: gradlew no encontrado en $PROJECT_DIR"
  exit 1
fi

./gradlew clean bundleRelease -Pandroid.targetSdkVersion="$TARGET_SDK"
echo "OK: AAB generado en app/build/outputs/bundle/release/"
