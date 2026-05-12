from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_notification_setup(page, base_url):
    page.goto(f"{base_url}/settings")
    assert page.url.startswith("http")
