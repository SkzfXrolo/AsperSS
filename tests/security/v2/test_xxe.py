from __future__ import annotations

import pytest


def test_xxe_placeholder(client):
    r = client.post("/api/xml/import", data="<!DOCTYPE x [ <!ENTITY e SYSTEM 'file:///etc/passwd'> ]><x>&e;</x>")
    if r.status_code == 404:
        pytest.skip("XML import endpoint ausente")
    assert r.status_code in {200, 400, 401, 403}
