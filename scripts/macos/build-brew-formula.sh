#!/usr/bin/env bash
set -euo pipefail

VERSION="${VERSION:-0.1.0}"
URL="${URL:-TBD_RELEASE_TARBALL_URL}"
SHA256="${SHA256:-TBD_SHA256}"
OUT="${OUT:-build/argus-scanner.rb}"

mkdir -p "$(dirname "$OUT")"
cat > "$OUT" <<EOF
class ArgusScanner < Formula
  desc "Argus Anti-Cheat scanner"
  homepage "TBD_HOMEPAGE"
  url "$URL"
  sha256 "$SHA256"
  version "$VERSION"

  def install
    bin.install "ArgusScanner"
  end
end
EOF

echo "OK: formula generada en $OUT"
