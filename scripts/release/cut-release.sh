#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then echo "Uso: cut-release.sh <version>"; exit 1; fi

git tag "v$VERSION"
scripts/build/gen-changelog.sh
echo "REVIEW: build all artifacts + upload GitHub Release."
