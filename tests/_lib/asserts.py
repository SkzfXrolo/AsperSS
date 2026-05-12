from __future__ import annotations


def assert_oracle_decision_valid(decision):
    assert 0.0 <= decision.score <= 1.0
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.action in {"none", "watch", "ss", "kick", "ban"}
    assert isinstance(decision.reasoning, str) and decision.reasoning.strip()


def assert_no_pii_leak(text: str):
    lowered = text.lower()
    assert "@gmail.com" not in lowered
    assert "password" not in lowered
