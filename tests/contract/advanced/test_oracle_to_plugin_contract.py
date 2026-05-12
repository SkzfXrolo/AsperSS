from __future__ import annotations

from argus_ai_oracle import evaluate


def test_oracle_output_contract_fields():
    d = evaluate({"violations": []})
    assert hasattr(d, "score")
    assert hasattr(d, "confidence")
    assert hasattr(d, "action")
