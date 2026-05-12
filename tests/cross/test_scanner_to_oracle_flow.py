from __future__ import annotations

from argus_ai_oracle import evaluate


def test_scanner_to_oracle_flow():
    scanner_findings = {"violations": [{"check_name": "autoclicker", "level": "HIGH", "age_seconds": 1}]}
    d = evaluate(scanner_findings)
    assert d.action in {"none", "watch", "kick", "ban"}
