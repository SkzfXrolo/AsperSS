#!/usr/bin/env bash
set -euo pipefail

MIN_GLIBC="${MIN_GLIBC:-2.31}"

if ! command -v ldd >/dev/null 2>&1; then
  echo "ERROR: ldd no disponible"
  exit 1
fi

VERSION="$(ldd --version | awk 'NR==1 {print $NF}')"
echo "glibc detectada: $VERSION"
echo "glibc minima requerida: $MIN_GLIBC"

lowest="$(printf '%s\n%s\n' "$MIN_GLIBC" "$VERSION" | sort -V | head -n1)"
if [[ "$lowest" != "$MIN_GLIBC" ]]; then
  echo "ERROR: glibc $VERSION es menor a $MIN_GLIBC"
  exit 1
fi

echo "OK: compatibilidad glibc validada."
