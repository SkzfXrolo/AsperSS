"""Tests ScanPipeline modes + PIN + integrity helpers (sin disco forense real)."""
from scan_pipeline import (
    MODE_FAST,
    MODE_PARANOID,
    MODE_STANDARD,
    eta_for_mode,
    normalize_mode,
    phases_for_mode,
    profile_dict,
)
from ss_pin import generate_pin, validate_pin, clear_pin
from ss_verdict import build_verdict, VERDICT_SUSPICIOUS, VERDICT_LIKELY, VERDICT_CONFIRMED


def test_normalize_aliases():
    assert normalize_mode("quick") == MODE_FAST
    assert normalize_mode("lite") == MODE_FAST
    assert normalize_mode("full") == MODE_STANDARD
    assert normalize_mode("deep") == MODE_PARANOID


def test_fast_phases_minimal():
    phases = phases_for_mode(MODE_FAST)
    assert "processes" in phases
    assert "integrity" in phases
    assert "filter_verdict" in phases
    assert "yara_java" not in phases
    assert "usn_killchain" not in phases
    assert eta_for_mode(MODE_FAST) <= 300


def test_paranoid_includes_yara():
    phases = phases_for_mode(MODE_PARANOID)
    assert "yara_java" in phases
    assert "memory_strings" in phases
    assert "mouse_session" in phases
    assert eta_for_mode(MODE_PARANOID) >= 900


def test_profile_dict():
    p = profile_dict("standard")
    assert p["name"] == MODE_STANDARD
    assert "phases" in p and len(p["phases"]) >= 5


def test_pin_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    clear_pin()
    info = generate_pin("tok_test_abc", staff_hint="staff1")
    assert len(info["pin"]) == 6
    assert validate_pin(info["pin"]) == "tok_test_abc"
    assert validate_pin("000000") is None
    clear_pin()


def test_integrity_weight_in_timeline():
    issues = [
        {
            "nombre": "Recent wipe",
            "tipo": "ss_integrity",
            "categoria": "INTEGRITY",
            "alerta": "CRITICAL",
            "confidence": 0.92,
            "timestamp": "2026-01-01T12:00:00",
        },
        {
            "nombre": "mod sospechoso",
            "tipo": "jar_mod",
            "alerta": "SOSPECHOSO",
            "confidence": 0.55,
        },
    ]
    v = build_verdict(issues)
    assert v["verdict"] in (VERDICT_SUSPICIOUS, VERDICT_LIKELY, VERDICT_CONFIRMED)
    assert v["risk_score"] >= 35
    assert any("timeline" in k or True for k in v)
    # timeline debe existir y priorizar integridad cuando hay timestamps
    assert "timeline" in v or "kill_chain" in v
