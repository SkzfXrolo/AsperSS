#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="${PLUGIN_DIR:-minecraft_plugin/argus-mc}"
JAR_PATTERN="${JAR_PATTERN:-target/argus-mc-*.jar}"

cd "$PLUGIN_DIR"
mvn -B -ntp clean package
JAR_FILE="$(ls $JAR_PATTERN | head -n1)"

jarsigner -keystore "${KEYSTORE_PATH:-TBD_KEYSTORE}" "$JAR_FILE" "${KEY_ALIAS:-TBD_ALIAS}" || true
echo "REVIEW: subir $JAR_FILE a SpigotMC/Modrinth/Hangar via API."
