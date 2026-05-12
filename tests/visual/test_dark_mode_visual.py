from __future__ import annotations

import pytest

from tests.visual.conftest import image_hash


@pytest.mark.visual
def test_dark_mode_visual(page, base_url, visual_dirs):
    baselines, actuals = visual_dirs
    page.goto(f"{base_url}/")
    page.evaluate("() => document.documentElement.setAttribute('data-theme', 'dark')")
    shot = page.screenshot(full_page=True)
    actuals.joinpath("dark_mode.png").write_bytes(shot)
    baseline = baselines / "dark_mode.png"
    if not baseline.exists():
        pytest.skip("Baseline no generado todavía")
    assert image_hash(shot) == image_hash(baseline.read_bytes())
