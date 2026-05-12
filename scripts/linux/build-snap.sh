#!/usr/bin/env bash
set -euo pipefail

mkdir -p build/snap
cat > build/snap/snapcraft.yaml <<'EOF'
name: argus-scanner
base: core22
version: '0.1.0'
summary: Argus scanner
description: Argus Anti-Cheat scanner desktop
grade: stable
confinement: strict
apps:
  argus-scanner:
    command: ArgusScanner
parts:
  argus:
    plugin: dump
    source: dist/
EOF
echo "OK: snapcraft.yaml generado en build/snap/"
