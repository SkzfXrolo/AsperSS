"""Combos multi-evidencia (_apply_combination_penalties)."""


class _App:
    def _apply_combination_penalties(self, issues):
        from main import ArgusApp
        return ArgusApp._apply_combination_penalties(self, issues)


def test_recycle_hash_plus_prefetch_combo():
    issues = [
        {"tipo": "recycle_hash_match", "alerta": "CRITICAL", "confidence": 0.96, "nombre": "h"},
        {"tipo": "prefetch_hack", "alerta": "SOSPECHOSO", "confidence": 0.8, "nombre": "p"},
    ]
    out = _App()._apply_combination_penalties(list(issues))
    assert any(i.get("combination_penalty") == "recycle_hash+execution" for i in out)


def test_remote_plus_ghost_combo():
    issues = [
        {"tipo": "remote_access_active", "alerta": "SOSPECHOSO", "confidence": 0.55, "nombre": "a"},
        {"tipo": "ghost_client_config", "alerta": "CRITICAL", "confidence": 0.9, "nombre": "g"},
    ]
    out = _App()._apply_combination_penalties(list(issues))
    assert any(i.get("combination_penalty") == "remote_help+cheat_signal" for i in out)
    rem = next(i for i in out if i["tipo"] == "remote_access_active")
    assert rem["alerta"] == "CRITICAL"
