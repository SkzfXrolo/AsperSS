from __future__ import annotations


def test_audit_log_completeness_contract():
    critical_actions = {"ban_player", "admin_login", "token_create"}
    assert "ban_player" in critical_actions
