from __future__ import annotations

import random

import pytest
from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from argus_ai_features import FEATURE_NAMES, extract_features


class FeaturesMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.evidence = {"violations": []}

    @initialize()
    def init_state(self):
        self.evidence = {"violations": []}

    @rule()
    def add_violation(self):
        self.evidence["violations"].append(
            {
                "check_name": random.choice(["reach", "speed", "killaura_multi", "autoclicker"]),
                "level": random.choice(["LOW", "MID", "HIGH", "CRITICAL"]),
                "age_seconds": random.randint(1, 500),
            }
        )

    @rule()
    def compute_features(self):
        fv = extract_features(self.evidence)
        assert len(fv) == len(FEATURE_NAMES)
        assert all(isinstance(x, (int, float)) for x in fv)

    @invariant()
    def violations_is_list(self):
        assert isinstance(self.evidence["violations"], list)


TestFeaturesMachine = FeaturesMachine.TestCase
TestFeaturesMachine.settings = settings(max_examples=120, stateful_step_count=20)


@pytest.mark.fuzz
def test_features_machine_collect_marker():
    assert True
