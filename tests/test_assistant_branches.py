from __future__ import annotations

import random

import argus_ai_assistant as a


def test_compare_with_neighbors_labels():
    out = a.compare_with_neighbors({"player_name": "Neo"}, [{"player_name": "X", "similarity": 0.9, "label": 1.0}], rng=random.Random(1))
    assert isinstance(out, str) and out.strip()


def test_ask_unknown_path():
    r = a.ask("???", resolve_player_ctx=lambda _: None, rng=random.Random(2))
    assert r["intent"] == "unknown"
