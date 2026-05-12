#!/usr/bin/env bash
set -euo pipefail

APP_NAME="${APP_NAME:-argus-scanner}"
APP_VERSION="${APP_VERSION:-0.1.0}"
RELEASE="${RELEASE:-1}"
SOURCE_BIN="${SOURCE_BIN:-dist/ArgusScanner}"
RPMROOT="${RPMROOT:-build/rpm}"

if [[ ! -x "$SOURCE_BIN" ]]; then
  echo "ERROR: no existe binario ejecutable en $SOURCE_BIN"
  exit 1
fi

if ! command -v rpmbuild >/dev/null 2>&1; then
  echo "ERROR: rpmbuild no esta instalado"
  exit 1
fi

mkdir -p "$RPMROOT"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
cp "$SOURCE_BIN" "$RPMROOT/SOURCES/$APP_NAME"

cat > "$RPMROOT/SPECS/$APP_NAME.spec" <<EOF
Name:           $APP_NAME
Version:        $APP_VERSION
Release:        $RELEASE%{?dist}
Summary:        Argus Anti-Cheat scanner desktop para Linux
License:        REVIEW
URL:            REVIEW
BuildArch:      x86_64
Requires:       glibc >= 2.31

%description
Cliente scanner desktop de Argus Anti-Cheat.

%install
mkdir -p %{buildroot}/usr/local/bin
install -m 0755 %{_sourcedir}/$APP_NAME %{buildroot}/usr/local/bin/$APP_NAME

%files
/usr/local/bin/$APP_NAME
EOF

rpmbuild --define "_topdir $(pwd)/$RPMROOT" -bb "$RPMROOT/SPECS/$APP_NAME.spec"
echo "OK: .rpm generado en $RPMROOT/RPMS/"
