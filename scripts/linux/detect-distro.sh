#!/usr/bin/env bash
set -euo pipefail

if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
  echo "ID=${ID:-unknown}"
  echo "ID_LIKE=${ID_LIKE:-unknown}"
  echo "VERSION_ID=${VERSION_ID:-unknown}"
  echo "PRETTY_NAME=${PRETTY_NAME:-unknown}"
  exit 0
fi

if command -v lsb_release >/dev/null 2>&1; then
  echo "ID=$(lsb_release -is | tr '[:upper:]' '[:lower:]')"
  echo "VERSION_ID=$(lsb_release -rs)"
  echo "PRETTY_NAME=$(lsb_release -ds)"
  exit 0
fi

echo "ID=unknown"
echo "VERSION_ID=unknown"
echo "PRETTY_NAME=unknown"
