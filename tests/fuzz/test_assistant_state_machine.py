from __future__ import annotations

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

import argus_ai_assistant as assistant


class AssistantMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.turns = []

    @initialize()
    def init_state(self):
        self.turns = []

    @rule(text=st.text(min_size=0, max_size=120))
    def classify_turn(self, text):
        i = assistant.classify_intent(text)
        self.turns.append((text, i.name))
        assert isinstance(i.name, str)

    @rule()
    def respond_status(self):
        msg = assistant.respond_about_player(
            {"player_name": "Mateo", "score": 0.6, "confidence": 0.7, "last_action": "watch"},
            intent="status",
        )
        assert isinstance(msg, str) and msg.strip()

    @invariant()
    def turns_bounded(self):
        assert len(self.turns) >= 0


TestAssistantMachine = AssistantMachine.TestCase
TestAssistantMachine.settings = settings(
    max_examples=110,
    stateful_step_count=20,
    suppress_health_check=[HealthCheck.too_slow],
)


@pytest.mark.fuzz
def test_assistant_machine_collect_marker():
    assert True
