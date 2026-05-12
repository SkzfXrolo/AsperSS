from __future__ import annotations

from argus_ai_oracle import evaluate


def test_oracle_contract_has_core_fields():
    d = evaluate({"violations": []})
    assert hasattr(d, "action")
    assert hasattr(d, "score")
    assert hasattr(d, "confidence")
