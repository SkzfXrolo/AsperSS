from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_enterprise_onboarding_smoke(page, base_url):
    page.goto(f"{base_url}/register")
    assert page.url.startswith("http")
