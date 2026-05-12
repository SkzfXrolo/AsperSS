#!/usr/bin/env bash
set -euo pipefail

echo "Build ARM64 (Raspberry Pi 4/5)"
python -m pip install --upgrade pip pyinstaller
PYINSTALLER_ARCH=arm64 pyinstaller --clean --noconfirm --onefile ArgusScanner.spec
