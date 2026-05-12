#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

python -m pytest --no-cov -m perf tests/perf/test_regression.py -q || true
echo "Actualiza manualmente tests/perf/baselines/oracle_v1.0.json con métricas nuevas si corresponde."
