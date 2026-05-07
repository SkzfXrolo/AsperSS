"""Convierte fondo negro del logo a transparente y recorta al sello.

Procesa logo.png para que el sello cobre quede flotando sin caja negra detras
y ocupando todo el bounding box (sin padding transparente innecesario).
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("[ERROR] Falta Pillow. Instala con: pip install Pillow")
    sys.exit(1)


def fix_logo(src: Path, dst: Path) -> None:
    img = Image.open(src).convert("RGBA")
    print(f"[INFO] Modo original: {img.mode}, tamano: {img.size}")

    pixels = img.load()
    w, h = img.size

    LOW = 18      # negro casi puro -> transparente
    HIGH = 60     # ya es color del logo -> opaco
    SPAN = HIGH - LOW

    cleared = 0
    softened = 0
    total = w * h

    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            if lum <= LOW:
                pixels[x, y] = (0, 0, 0, 0)
                cleared += 1
            elif lum < HIGH:
                ratio = (lum - LOW) / SPAN
                new_a = int(a * ratio)
                pixels[x, y] = (r, g, b, new_a)
                softened += 1

    print(f"[INFO] Pixels totalmente transparentes: {cleared:,} ({cleared*100/total:.1f}%)")
    print(f"[INFO] Pixels con alpha suavizado:      {softened:,} ({softened*100/total:.1f}%)")

    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        print(f"[INFO] Recortado al bbox: {bbox} -> nuevo tamano {img.size}")

    bw, bh = img.size
    side = max(bw, bh)
    pad_x = (side - bw) // 2
    pad_y = (side - bh) // 2
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, (pad_x, pad_y))
    print(f"[INFO] Centrado en lienzo cuadrado: {square.size}")

    if side > 1024:
        square.thumbnail((1024, 1024), Image.LANCZOS)
        print(f"[INFO] Reescalado a {square.size}")

    square.save(dst, "PNG", optimize=True)
    print(f"[OK] Guardado en {dst} ({dst.stat().st_size:,} bytes)")


def main() -> int:
    base = Path(__file__).resolve().parent.parent
    src = base / "web_app" / "static" / "img" / "logo.png"
    if not src.exists():
        print(f"[ERROR] No existe {src}")
        return 1

    backup = src.with_suffix(".png.bak")
    if backup.exists():
        src.write_bytes(backup.read_bytes())
        print(f"[INFO] Restaurado desde backup para procesar de cero")
    else:
        backup.write_bytes(src.read_bytes())
        print(f"[INFO] Backup creado: {backup}")

    fix_logo(src, src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
