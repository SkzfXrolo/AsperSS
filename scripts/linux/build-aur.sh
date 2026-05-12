#!/usr/bin/env bash
set -euo pipefail

mkdir -p build/aur
cat > build/aur/PKGBUILD <<'EOF'
pkgname=argus-scanner
pkgver=0.1.0
pkgrel=1
arch=('x86_64')
license=('REVIEW')
source=('TBD_URL')
sha256sums=('TBD')
package() {
  install -Dm755 ArgusScanner "$pkgdir/usr/bin/ArgusScanner"
}
EOF
echo "OK: PKGBUILD generado en build/aur/"
