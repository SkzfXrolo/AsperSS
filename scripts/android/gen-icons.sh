#!/usr/bin/env bash
set -euo pipefail

SRC_ICON="${1:-mobile/argus_android/assets/icon-foreground.png}"
OUT_DIR="${2:-mobile/argus_android/app/src/main/res}"

if ! command -v convert >/dev/null 2>&1; then
  echo "ERROR: ImageMagick 'convert' no instalado"
  exit 1
fi

if [[ ! -f "$SRC_ICON" ]]; then
  echo "ERROR: icono base no encontrado: $SRC_ICON"
  exit 1
fi

declare -A sizes=(
  [mipmap-mdpi]=108
  [mipmap-hdpi]=162
  [mipmap-xhdpi]=216
  [mipmap-xxhdpi]=324
  [mipmap-xxxhdpi]=432
)

for bucket in "${!sizes[@]}"; do
  size="${sizes[$bucket]}"
  mkdir -p "$OUT_DIR/$bucket"
  convert "$SRC_ICON" -resize "${size}x${size}" "$OUT_DIR/$bucket/ic_launcher_foreground.png"
done

echo "OK: iconos adaptivos generados en $OUT_DIR/mipmap-*"
