#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-argus-scanner}"
APP_VERSION="${APP_VERSION:-0.1.0}"
SOURCE_BIN="${SOURCE_BIN:-dist/ArgusScanner}"
WORKDIR="${WORKDIR:-build/appimage}"

if [[ ! -x "$SOURCE_BIN" ]]; then
  echo "ERROR: no existe binario ejecutable en $SOURCE_BIN"
  exit 1
fi

mkdir -p "$WORKDIR/AppDir/usr/bin" "$WORKDIR/out"
cp "$SOURCE_BIN" "$WORKDIR/AppDir/usr/bin/$APP_NAME"

cat > "$WORKDIR/AppDir/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Argus Scanner
Exec=$APP_NAME
Icon=$APP_NAME
Categories=Utility;Security;
EOF

if [[ -f "logo/argus.png" ]]; then
  cp "logo/argus.png" "$WORKDIR/AppDir/$APP_NAME.png"
fi

if ! command -v appimagetool >/dev/null 2>&1; then
  echo "ERROR: appimagetool no esta instalado"
  echo "Instala appimagetool en el runner Linux antes de ejecutar este script."
  exit 1
fi

appimagetool "$WORKDIR/AppDir" "$WORKDIR/out/${APP_NAME}-${APP_VERSION}-x86_64.AppImage"
echo "OK: AppImage generado en $WORKDIR/out/"
