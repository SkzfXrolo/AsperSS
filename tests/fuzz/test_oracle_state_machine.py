from __future__ import annotations

import random

import pytest
from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from argus_ai_oracle import evaluate


class OracleMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.violations = []
        self.last_score = 0.0

    @initialize()
    def init_state(self):
        self.violations = []
        self.last_score = 0.0

    @rule()
    def add_low(self):
        self.violations.append({"check_name": "reach", "level": "LOW", "age_seconds": random.randint(1, 50)})

    @rule()
    def add_mid(self):
        self.violations.append({"check_name": "speed", "level": "MID", "age_seconds": random.randint(1, 50)})

    @rule()
    def add_high(self):
        self.violations.append({"check_name": "killaura_no_swing", "level": "HIGH", "age_seconds": random.randint(1, 50)})

    @rule()
    def eval_now(self):
        d = evaluate({"violations": list(self.violations), "current_score": self.last_score})
        self.last_score = d.score
        assert 0.0 <= d.score <= 1.0
        assert d.action in {"none", "watch", "ss", "kick", "ban"}

    @invariant()
    def score_bounded(self):
        assert 0.0 <= self.last_score <= 1.0


TestOracleMachine = OracleMachine.TestCase
TestOracleMachine.settings = settings(max_examples=120, stateful_step_count=25)


@pytest.mark.fuzz
def test_oracle_machine_collect_marker():
    assert True
