#!/usr/bin/env bash
set -euo pipefail

pybabel compile -d locales
echo "OK: traducciones compiladas."
