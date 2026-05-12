#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
if [[ -f requirements.txt ]]; then pip install -r requirements.txt; fi
echo "OK: entorno dev inicializado."
