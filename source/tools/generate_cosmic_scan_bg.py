#!/usr/bin/env python3
"""Genera assets/cosmic-scan-bg.gif — fondo animado para la pantalla de escaneo."""
from __future__ import annotations

import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

W, H = 620, 440
N_FRAMES = 36
DURATION_MS = 85
OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'cosmic-scan-bg.gif')

random.seed(0xA96C5)
STARS = [
    (random.randint(0, W - 1), random.randint(0, H - 1), random.uniform(0.15, 1.0), random.random() * 6.28)
    for _ in range(160)
]

BLOBS = [
    (0.22, 0.28, 0.42, (21, 18, 42, 200)),
    (0.72, 0.22, 0.38, (26, 16, 56, 190)),
    (0.48, 0.62, 0.48, (12, 20, 40, 175)),
    (0.35, 0.55, 0.28, (18, 24, 48, 140)),
    (0.58, 0.38, 0.22, (60, 40, 120, 90)),
]


def _blob_layer(t: float) -> Image.Image:
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, 'RGBA')
    for i, (nx, ny, nr, col) in enumerate(BLOBS):
        phase = t + i * 0.9
        cx = int(W * nx + 14 * math.sin(phase * 0.7))
        cy = int(H * ny + 10 * math.cos(phase * 0.55))
        r = int(min(W, H) * nr)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    return layer.filter(ImageFilter.GaussianBlur(radius=28))


def _stars_layer(t: float) -> Image.Image:
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, 'RGBA')
    for x, y, br, ph in STARS:
        pulse = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 2.2 + ph))
        a = int(255 * br * pulse)
        if a < 20:
            continue
        tint = (200, 210, 255, a) if br > 0.55 else (140, 150, 220, a)
        draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=tint)
    return layer


def make_frame(i: float) -> Image.Image:
    t = (i / N_FRAMES) * math.pi * 2
    base = Image.new('RGB', (W, H), (4, 3, 14))
    nebula = _blob_layer(t)
    stars = _stars_layer(t)
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow, 'RGBA')
    gdraw.ellipse(
        (W * 0.15, H * 0.1, W * 0.85, H * 0.75),
        fill=(70, 60, 140, 35),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=40))
    comp = Image.alpha_composite(base.convert('RGBA'), nebula)
    comp = Image.alpha_composite(comp, glow)
    comp = Image.alpha_composite(comp, stars)
    return comp.convert('RGB')


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    frames = [make_frame(i) for i in range(N_FRAMES)]
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=DURATION_MS,
        loop=0,
        optimize=True,
    )
    print(f'OK: {OUT} ({N_FRAMES} frames, {W}x{H})')


if __name__ == '__main__':
    main()
