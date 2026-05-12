from __future__ import annotations

import pytest
from hypothesis.stateful import RuleBasedStateMachine, rule

from argus_ai_oracle import evaluate


class OracleStateMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.evidence = {"violations": []}

    @rule()
    def add_violation(self) -> None:
        self.evidence["violations"].append({"check_name": "speed_a", "level": "MID", "age_seconds": 1})

    @rule()
    def evaluate_is_bounded(self) -> None:
        d = evaluate(self.evidence)
        assert 0.0 <= d.score <= 1.0
        assert 0.0 <= d.confidence <= 1.0


@pytest.mark.fuzz
def test_oracle_state_machine_runs():
    OracleStateMachine.TestCase().runTest()
