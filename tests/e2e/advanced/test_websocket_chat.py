from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_websocket_chat_smoke(page, base_url):
    page.goto(f"{base_url}/panel")
    assert page.locator("body").count() == 1
