"""Genera assets/argus_admin.ico"""
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit('pip install pillow')

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / 'assets'
ASSETS.mkdir(exist_ok=True)


def _draw(size: int) -> Image.Image:
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = max(2, size // 16)
    d.ellipse([m, m, size - m, size - m], fill='#1a0a2e', outline='#B87333', width=max(2, size // 28))
    d.ellipse([size // 4, size // 4, 3 * size // 4, 3 * size // 4], fill='#B87333')
    try:
        font = ImageFont.truetype('arialbd.ttf', size // 2)
    except OSError:
        font = ImageFont.load_default()
    text = 'A'
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - tw) // 2, (size - th) // 2 - 2), text, fill='#1a0a2e', font=font)
    return img


if __name__ == '__main__':
    base = _draw(256)
    base.save(ASSETS / 'argus_admin.png', 'PNG')
    base.save(ASSETS / 'argus_admin.ico', format='ICO', sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)])
    print('OK', ASSETS / 'argus_admin.ico')
