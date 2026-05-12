from __future__ import annotations

from argus_ai_oracle import merge_action_with_existing


def test_plugin_to_web_contract_action_merge():
    assert merge_action_with_existing("ban", "kick") == "ban"
    assert merge_action_with_existing("watch", "ban") == "ban"
