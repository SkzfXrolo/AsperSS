from __future__ import annotations

import argus_ai_assistant as assistant


def test_status_templates_have_minimum_neutral_and_sarcastic():
    assert len(assistant.T_STATUS_CLEAN_NEUTRAL) >= 3
    assert len(assistant.T_STATUS_CLEAN_SARCASTIC) >= 2
    assert len(assistant.T_STATUS_WATCH_NEUTRAL) >= 3
    assert len(assistant.T_STATUS_WATCH_SARCASTIC) >= 2
    assert len(assistant.T_STATUS_KICK_NEUTRAL) >= 3
    assert len(assistant.T_STATUS_KICK_SARCASTIC) >= 2
    assert len(assistant.T_STATUS_BAN_NEUTRAL) >= 3
    assert len(assistant.T_STATUS_BAN_SARCASTIC) >= 2


def test_generic_intents_have_minimum_templates():
    assert len(assistant.T_GREETING_NEUTRAL) >= 3
    assert len(assistant.T_GREETING_SARCASTIC) >= 2
    assert len(assistant.T_HISTORY_NEUTRAL) >= 3
    assert len(assistant.T_HISTORY_DIRTY_SARCASTIC) >= 2
