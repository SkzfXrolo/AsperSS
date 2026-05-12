from __future__ import annotations

from typing import Any


def calculate_trust_score(metrics: dict[str, Any]) -> tuple[float, dict[str, float]]:
    age_days = float(metrics.get("account_age_days") or 0.0)
    scans = float(metrics.get("scans_count") or 0.0)
    oracle_flags = float(metrics.get("oracle_flags") or 0.0)
    mfa_enabled = 1.0 if metrics.get("mfa_enabled") else 0.0
    profile_ok = 1.0 if metrics.get("profile_complete") else 0.0

    factors = {
        "account_age": min(30.0, age_days / 12.0),
        "scan_history": min(25.0, scans * 0.5),
        "oracle_penalty": min(30.0, oracle_flags * 1.5),
        "mfa_bonus": 10.0 * mfa_enabled,
        "profile_bonus": 5.0 * profile_ok,
    }
    score = 50.0 + factors["account_age"] + factors["scan_history"] - factors["oracle_penalty"] + factors["mfa_bonus"] + factors["profile_bonus"]
    score = max(0.0, min(100.0, score))
    return score, factors
