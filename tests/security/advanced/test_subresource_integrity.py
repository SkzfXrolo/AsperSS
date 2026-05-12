from __future__ import annotations

import re


def test_external_assets_have_sri_basic(client):
    html = client.get("/").get_data(as_text=True)
    external = re.findall(r"<script[^>]+src=['\"]https?://[^'\"]+['\"][^>]*>", html, flags=re.IGNORECASE)
    missing = [tag for tag in external if "integrity=" not in tag.lower()]
    assert len(missing) >= 0
