#!/usr/bin/env bash
set -euo pipefail

read -r -p "Ruta backup a restaurar: " BACKUP_PATH
echo "REVIEW: restaurar DB y archivos desde $BACKUP_PATH"
