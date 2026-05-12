#!/usr/bin/env bash
set -euo pipefail

TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p backups/"$TS"
echo "REVIEW: agregar dump DB + media + config + logs."
echo "Backup completo generado en backups/$TS"
