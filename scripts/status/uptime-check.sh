#!/usr/bin/env bash
set -euo pipefail

URLS=("https://asperss.onrender.com/healthz" "https://asperss.onrender.com/")
for url in "${URLS[@]}"; do
  if curl -fsS "$url" >/dev/null; then
    echo "UP $url"
  else
    echo "DOWN $url"
  fi
done
