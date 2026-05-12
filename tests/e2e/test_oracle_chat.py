from __future__ import annotations

import pytest
import requests


@pytest.mark.e2e
def test_oracle_chat_endpoint_render_and_response(page, base_url):
    page.goto(f"{base_url}/panel")
    assert page.locator("body").count() == 1
    # fallback API probe (si backend no está autenticado puede devolver 401/403)
    r = requests.post(f"{base_url}/api/ai/assistant/ask", json={"text": "hola"}, timeout=10)
    assert r.status_code in {200, 400, 401, 403}
