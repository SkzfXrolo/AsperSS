#!/usr/bin/env bash
set -euo pipefail

echo "Build ARMHF (Raspberry Pi 3)"
python -m pip install --upgrade pip pyinstaller
PYINSTALLER_ARCH=armv7l pyinstaller --clean --noconfirm --onefile ArgusScanner.spec
