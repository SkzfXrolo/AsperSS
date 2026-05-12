from __future__ import annotations

import time

import pytest

from argus_ai_assistant import classify_intent


@pytest.mark.perf
def test_assistant_responsiveness():
    start = time.perf_counter()
    for _ in range(500):
        classify_intent("hola como va mateo")
    assert (time.perf_counter() - start) < 1.0
