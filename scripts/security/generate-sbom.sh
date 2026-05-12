#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${ROOT_DIR}/security-artifacts/sbom"
mkdir -p "${OUT_DIR}"

echo "[sbom] output dir: ${OUT_DIR}"

echo "[sbom] Python (CycloneDX)"
if command -v cyclonedx-py >/dev/null 2>&1; then
  cyclonedx-py requirements "${ROOT_DIR}/web_app/requirements.txt" \
    -o "${OUT_DIR}/sbom-python-web_app.json" || true
else
  echo "[sbom] cyclonedx-py not installed"
fi

echo "[sbom] Java plugin (Maven CycloneDX)"
if command -v mvn >/dev/null 2>&1; then
  mvn -f "${ROOT_DIR}/minecraft_plugin/argus-mc/pom.xml" -q \
    org.cyclonedx:cyclonedx-maven-plugin:makeAggregateBom || true
  if [ -f "${ROOT_DIR}/minecraft_plugin/argus-mc/target/bom.xml" ]; then
    cp "${ROOT_DIR}/minecraft_plugin/argus-mc/target/bom.xml" "${OUT_DIR}/sbom-java-plugin.xml"
  fi
else
  echo "[sbom] mvn not installed"
fi

echo "[sbom] JS panel (CycloneDX npm)"
if command -v npx >/dev/null 2>&1; then
  (cd "${ROOT_DIR}/web_app" && npx @cyclonedx/bom -o "${OUT_DIR}/sbom-js-web_app.xml") || true
else
  echo "[sbom] npx not installed"
fi

echo "[sbom] done"
