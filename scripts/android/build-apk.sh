#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-mobile/argus_android}"
TARGET_SDK="${TARGET_SDK:-34}"

echo "Build APK release (targetSdk=$TARGET_SDK)"
cd "$PROJECT_DIR"

if [[ ! -f "gradlew" ]]; then
  echo "ERROR: gradlew no encontrado en $PROJECT_DIR"
  exit 1
fi

./gradlew clean assembleRelease -Pandroid.targetSdkVersion="$TARGET_SDK"
echo "OK: APK generado en app/build/outputs/apk/release/"
