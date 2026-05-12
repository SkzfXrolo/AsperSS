#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${ROOT_DIR}/security-artifacts/sast"
mkdir -p "${OUT_DIR}"

echo '{"tools":[]}' > "${OUT_DIR}/summary.json"

run_and_capture() {
  local tool="$1"
  local cmd="$2"
  local out="${OUT_DIR}/${tool}.json"
  echo "[sast] ${tool}"
  if eval "${cmd}" > "${out}" 2>/dev/null; then
    echo "[sast] ${tool} ok"
  else
    echo "[sast] ${tool} returned non-zero (captured)"
  fi
}

run_and_capture "bandit" "bandit -r ${ROOT_DIR}/web_app ${ROOT_DIR}/source -f json"
run_and_capture "semgrep" "semgrep --config ${ROOT_DIR}/scripts/security/sast-config.yml --json ${ROOT_DIR}/web_app ${ROOT_DIR}/source ${ROOT_DIR}/minecraft_plugin"
run_and_capture "gitleaks" "gitleaks detect --source ${ROOT_DIR} --report-format json --report-path /dev/stdout"
run_and_capture "pip-audit" "pip-audit -r ${ROOT_DIR}/web_app/requirements.txt -f json"
run_and_capture "safety" "safety check -r ${ROOT_DIR}/web_app/requirements.txt --json"

echo "[sast] artifacts in ${OUT_DIR}"
