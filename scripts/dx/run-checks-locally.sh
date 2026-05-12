#!/usr/bin/env bash
set -euo pipefail

echo "Lint/format/tests/security local checks"
pytest -q
echo "REVIEW: agregar linters y escáneres concretos del repo."
