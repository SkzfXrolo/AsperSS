from __future__ import annotations

import pytest


@pytest.mark.perf
def test_panel_render_budget_placeholder(client):
    r = client.get("/panel")
    assert r.status_code in {200, 302}
