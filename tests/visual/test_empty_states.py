from __future__ import annotations

import pytest

from tests.visual.conftest import image_hash


@pytest.mark.visual
def test_empty_state_visual(page, base_url, visual_dirs):
    baselines, actuals = visual_dirs
    page.goto(f"{base_url}/panel?empty=1")
    shot = page.screenshot(full_page=True)
    actuals.joinpath("empty_state.png").write_bytes(shot)
    baseline = baselines / "empty_state.png"
    if not baseline.exists():
        pytest.skip("Baseline no generado todavía")
    assert image_hash(shot) == image_hash(baseline.read_bytes())
