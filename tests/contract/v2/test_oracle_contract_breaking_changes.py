from __future__ import annotations

from argus_ai_oracle import evaluate


def test_oracle_contract_no_breaking_fields():
    out = evaluate({"violations": []})
    assert hasattr(out, "action")
    assert hasattr(out, "score")
    assert hasattr(out, "confidence")
