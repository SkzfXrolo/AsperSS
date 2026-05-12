from __future__ import annotations

import random

import argus_ai_assistant as A


def test_build_slots_from_context_has_expected_keys():
    slots = A._build_slots_from_context({"player_name": "Neo", "score": 0.8, "confidence": 0.9})
    assert slots["player"] == "Neo"
    assert "score_pct" in slots


def test_compare_with_neighbors_no_neighbors_message():
    out = A.compare_with_neighbors({"player_name": "Neo"}, [], rng=random.Random(1))
    assert isinstance(out, str) and out.strip()


def test_ask_greeting_path():
    out = A.ask("hola", resolve_player_ctx=lambda _: None, rng=random.Random(2))
    assert out["intent"] == "greeting"


def test_ask_daily_summary_path():
    out = A.ask(
        "resumen del dia",
        resolve_player_ctx=lambda _: None,
        get_daily_stats=lambda **kwargs: {"date": "hoy", "evaluations_count": 1},
        rng=random.Random(3),
    )
    assert out["intent"] == "daily_summary"


def test_llm_polish_without_key_returns_same_text(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    text = "respuesta base"
    assert A.llm_polish(text) == text


def test_safe_text_sanitizes_whitespace():
    s = A.safe_text(" hola   mundo \n\n")
    assert s == "hola mundo"
