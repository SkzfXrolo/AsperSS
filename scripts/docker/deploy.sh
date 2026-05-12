#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-TBD_HOST}"
REMOTE_USER="${REMOTE_USER:-TBD_USER}"
REMOTE_PATH="${REMOTE_PATH:-/opt/argus}"

rsync -avz docker/ "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/docker/"
ssh "${REMOTE_USER}@${REMOTE_HOST}" "cd ${REMOTE_PATH}/docker && docker compose pull && docker compose up -d"
echo "OK: deploy remoto aplicado en ${REMOTE_HOST}"
