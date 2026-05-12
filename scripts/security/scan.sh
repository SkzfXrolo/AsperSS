#!/usr/bin/env bash
set -euo pipefail

echo "[security] Running Bandit"
if command -v bandit >/dev/null 2>&1; then
  bandit -q -r web_app source || true
else
  echo "[security] bandit not installed"
fi

echo "[security] Running Safety"
if command -v safety >/dev/null 2>&1; then
  safety check -r web_app/requirements.txt || true
else
  echo "[security] safety not installed"
fi

echo "[security] Running Semgrep"
if command -v semgrep >/dev/null 2>&1; then
  semgrep --config auto web_app source minecraft_plugin || true
else
  echo "[security] semgrep not installed"
fi

echo "[security] Done"
