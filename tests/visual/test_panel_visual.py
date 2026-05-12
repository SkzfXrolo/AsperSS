from __future__ import annotations

import pytest

from tests.visual.conftest import image_hash


@pytest.mark.visual
def test_panel_main_visual(page, base_url, visual_dirs):
    baselines, actuals = visual_dirs
    page.goto(f"{base_url}/panel")
    shot = page.screenshot(full_page=True)
    actual = actuals / "panel_main.png"
    actual.write_bytes(shot)
    baseline = baselines / "panel_main.png"
    if not baseline.exists():
        pytest.skip("Baseline no generado todavía")
    assert image_hash(shot) == image_hash(baseline.read_bytes())
