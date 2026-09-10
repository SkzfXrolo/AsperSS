"""Tests Top-N results_display + ranking staff."""
from results_display import rank_issues, split_top_n, format_issue_line


def test_verdict_always_in_top():
    issues = [
        {"tipo": "prefetch_hack", "alerta": "CRITICAL", "confidence": 0.9, "nombre": "pf"},
        {"tipo": "ss_verdict", "alerta": "CRITICAL", "confidence": 1.0, "nombre": "CHEATER",
         "verdict_data": {"verdict": "CHEATER", "risk_score": 90}},
        {"tipo": "normal_noise", "alerta": "NORMAL", "confidence": 0.1, "nombre": "noise"},
    ]
    top, other = split_top_n(issues, n=5)
    assert top[0]["tipo"] == "ss_verdict"
    assert any(i["tipo"] == "prefetch_hack" for i in top)
    assert any(i["tipo"] == "normal_noise" for i in other) or len(top) + len(other) == 3


def test_rank_boosts_forensic():
    ranked = rank_issues([
        {"tipo": "browser_download", "alerta": "SOSPECHOSO", "confidence": 0.9},
        {"tipo": "userassist_suspicious", "alerta": "CRITICAL", "confidence": 0.8},
    ])
    assert ranked[0]["tipo"] == "userassist_suspicious"


def test_format_issue_line_includes_explicacion():
    line = format_issue_line(
        {
            "nombre": "Hack",
            "tipo": "recycle_hack",
            "alerta": "CRITICAL",
            "explicacion": "En papelera",
            "timestamp": "2026-07-26T12:00:00",
        },
        1,
    )
    assert "por qué: En papelera" in line
    assert "t=2026-07-26T12:00:00" in line
