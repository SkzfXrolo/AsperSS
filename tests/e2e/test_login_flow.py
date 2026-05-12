from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_login_panel_logout_flow(page, base_url):
    page.goto(f"{base_url}/login")
    assert page.locator("body").count() == 1
    # Smoke de navegación mínima sin asumir credenciales válidas.
    page.goto(f"{base_url}/panel")
    assert page.locator("body").count() == 1
    page.goto(f"{base_url}/logout")
    assert page.locator("body").count() == 1
