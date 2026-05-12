from __future__ import annotations

import pytest


@pytest.mark.visual
@pytest.mark.parametrize(
    "name,size",
    [
        ("mobile", {"width": 390, "height": 844}),
        ("tablet", {"width": 768, "height": 1024}),
        ("desktop", {"width": 1440, "height": 900}),
    ],
)
def test_responsive_visual(page, base_url, visual_dirs, name, size):
    _baselines, actuals = visual_dirs
    page.set_viewport_size(size)
    page.goto(f"{base_url}/")
    shot = page.screenshot(full_page=True)
    actuals.joinpath(f"responsive_{name}.png").write_bytes(shot)
    assert len(shot) > 0
