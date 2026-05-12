#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://asperss.onrender.com}"
OUT="${OUT:-build/sitemap.xml}"

mkdir -p "$(dirname "$OUT")"
cat > "$OUT" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>${BASE_URL}/</loc></url>
  <url><loc>${BASE_URL}/descargar</loc></url>
  <url><loc>${BASE_URL}/descargar/plugin</loc></url>
</urlset>
EOF

echo "OK: sitemap generado en $OUT"
