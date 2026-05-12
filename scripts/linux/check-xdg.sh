#!/usr/bin/env bash
set -euo pipefail

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

echo "XDG_CONFIG_HOME=$XDG_CONFIG_HOME"
echo "XDG_CACHE_HOME=$XDG_CACHE_HOME"
echo "XDG_STATE_HOME=$XDG_STATE_HOME"

for dir in "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_STATE_HOME"; do
  if [[ ! -d "$dir" ]]; then
    echo "WARN: ruta no existe todavia -> $dir"
  fi
done

echo "OK: chequeo de entorno XDG finalizado."
