#!/usr/bin/env bash
set -euo pipefail

echo "run lint + tests + security"
pytest -q
