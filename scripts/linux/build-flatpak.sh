#!/usr/bin/env bash
set -euo pipefail

mkdir -p build/flatpak
cat > build/flatpak/com.argus.Scanner.json <<'EOF'
{
  "app-id": "com.argus.Scanner",
  "runtime": "org.freedesktop.Platform",
  "runtime-version": "23.08",
  "sdk": "org.freedesktop.Sdk",
  "command": "ArgusScanner",
  "modules": []
}
EOF
echo "OK: manifest flatpak generado en build/flatpak/"
