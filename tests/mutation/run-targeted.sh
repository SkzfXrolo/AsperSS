#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-web_app/argus_ai_oracle.py}"
python -m pip install -r tests/requirements-test.txt
mutmut run --paths-to-mutate "$TARGET"
mutmut results
