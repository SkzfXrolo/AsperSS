from __future__ import annotations

import pytest


def test_websocket_chat_endpoint_placeholder(client):
    r = client.get("/api/ws/chat")
    if r.status_code == 404:
        pytest.skip("WebSocket chat v2 pendiente de D")
    assert r.status_code in {200, 400, 401, 403}
