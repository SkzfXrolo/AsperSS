#!/usr/bin/env bash
set -euo pipefail

python -m pytest tests/ -q -m "not integration and not contract and not e2e and not visual"
python -m pytest tests/integration -q
python -m pytest tests/contract -q
python -m pytest tests/e2e -q -m e2e
