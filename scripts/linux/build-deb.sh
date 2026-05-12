#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-argus-scanner}"
APP_VERSION="${APP_VERSION:-0.1.0}"
ARCH="${ARCH:-amd64}"
SOURCE_BIN="${SOURCE_BIN:-dist/ArgusScanner}"
BUILD_ROOT="${BUILD_ROOT:-build/deb}"
PKG_ROOT="$BUILD_ROOT/${APP_NAME}_${APP_VERSION}_${ARCH}"

if [[ ! -x "$SOURCE_BIN" ]]; then
  echo "ERROR: no existe binario ejecutable en $SOURCE_BIN"
  exit 1
fi

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "ERROR: dpkg-deb no esta disponible"
  exit 1
fi

mkdir -p "$PKG_ROOT/DEBIAN" "$PKG_ROOT/usr/local/bin"
cp "$SOURCE_BIN" "$PKG_ROOT/usr/local/bin/$APP_NAME"

cat > "$PKG_ROOT/DEBIAN/control" <<EOF
Package: $APP_NAME
Version: $APP_VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: Argus Projects <REVIEW: definir email>
Depends: libc6 (>= 2.31)
Description: Argus Anti-Cheat scanner desktop para Linux
EOF

mkdir -p "$BUILD_ROOT/out"
dpkg-deb --build "$PKG_ROOT" "$BUILD_ROOT/out/${APP_NAME}_${APP_VERSION}_${ARCH}.deb"
echo "OK: .deb generado en $BUILD_ROOT/out/"
