from __future__ import annotations

import pytest
from hypothesis import given, strategies as st


@pytest.mark.fuzz
@given(st.dictionaries(st.text(min_size=1, max_size=10), st.text(max_size=20), max_size=8))
def test_random_payloads_do_not_crash_client(client, payload):
    r = client.post("/api/oracle/evaluate", json=payload)
    assert r.status_code in {200, 400, 401, 403, 404, 422, 500}
