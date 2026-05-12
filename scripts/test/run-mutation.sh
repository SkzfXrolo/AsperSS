#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

python -m pip install -r tests/requirements-test.txt

mutmut run --paths-to-mutate web_app/argus_ai_oracle.py
mutmut run --paths-to-mutate web_app/argus_ai_features.py
mutmut run --paths-to-mutate web_app/argus_ai_trainer.py
mutmut run --paths-to-mutate web_app/argus_ai_labeler.py
mutmut run --paths-to-mutate web_app/argus_ai_assistant.py

mutmut results | tee tests/mutation/mutmut-results.txt
