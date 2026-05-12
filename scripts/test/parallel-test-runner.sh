#!/usr/bin/env bash
set -euo pipefail

python -m pytest tests/property -q &
P1=$!
python -m pytest tests/security -q &
P2=$!
python -m pytest tests/monitoring -q &
P3=$!

wait "$P1" "$P2" "$P3"
