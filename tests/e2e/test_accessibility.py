from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_accessibility_basic_landmarks(page, base_url):
    page.goto(f"{base_url}/")
    main_or_body = page.locator("main, body")
    assert main_or_body.count() >= 1
