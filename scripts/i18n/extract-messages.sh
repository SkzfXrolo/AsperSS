#!/usr/bin/env bash
set -euo pipefail

pybabel extract -F babel.cfg -o locales/messages.pot .
echo "OK: mensajes extraídos."
