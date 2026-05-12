#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

mkdir -p tests/fuzz/afl/in tests/fuzz/afl/out
echo '{"violations":[{"check_name":"reach","level":"MID","age_seconds":10}]}' > tests/fuzz/afl/in/seed.json

python tests/fuzz/afl/oracle_target.py < tests/fuzz/afl/in/seed.json
echo "Seed ejecutada. Para campaña AFL real, correr afl-fuzz con este target."
