"""Tests del veredicto SS y pack de integridad (sin tocar disco real)."""
from ss_verdict import (
    VERDICT_CLEAN,
    VERDICT_CONFIRMED,
    VERDICT_LIKELY,
    VERDICT_SUSPICIOUS,
    build_verdict,
    verdict_issue,
)


def test_clean_machine():
    v = build_verdict([])
    assert v["verdict"] == VERDICT_CLEAN
    assert v["risk_score"] < 35


def test_integrity_alone_is_suspicious():
    issues = [{
        "nombre": "Prefetch casi vacío (8 archivos .pf)",
        "tipo": "ss_integrity",
        "categoria": "INTEGRITY",
        "alerta": "CRITICAL",
        "confidence": 0.9,
        "detected_patterns": ["integrity:prefetch_count:8"],
    }]
    v = build_verdict(issues)
    assert v["verdict"] in (VERDICT_SUSPICIOUS, VERDICT_LIKELY, VERDICT_CONFIRMED)
    assert v["risk_score"] >= 35
    assert any("Integridad" in r or "integridad" in r.lower() for r in v["reasons"])


def test_kill_chain_confirmed():
    issues = [
        {
            "nombre": "Vape Lite en Prefetch",
            "tipo": "prefetch_hack",
            "alerta": "CRITICAL",
            "confidence": 0.95,
            "ruta": r"C:\Windows\Prefetch\VAPELITE.EXE-ABC.pf",
        },
        {
            "nombre": "PowerShell bypass wipe",
            "tipo": "ss_integrity",
            "categoria": "INTEGRITY",
            "alerta": "CRITICAL",
            "confidence": 0.93,
        },
        {
            "nombre": "DLL inject en javaw",
            "tipo": "dll_injection",
            "alerta": "SOSPECHOSO",
            "confidence": 0.8,
        },
    ]
    v = build_verdict(issues)
    assert v["verdict"] in (VERDICT_LIKELY, VERDICT_CONFIRMED)
    assert v["risk_score"] >= 60
    assert len(v["kill_chain"]) >= 2
    vi = verdict_issue(v)
    assert "VEREDICTO ARGUS" in vi["nombre"]
    assert vi["tipo"] == "ss_verdict"


def test_staff_action_present():
    v = build_verdict([])
    assert "staff_action" in v
    assert v["summary_es"]


def test_timeline_includes_integrity_events():
    issues = [
        {
            "nombre": "Prefetch wipe",
            "tipo": "ss_integrity",
            "categoria": "INTEGRITY",
            "alerta": "CRITICAL",
            "confidence": 0.9,
            "timestamp": "2026-07-01T10:00:00",
            "detected_patterns": ["integrity:prefetch_wipe"],
        },
        {
            "nombre": "BAM vape",
            "tipo": "bam_execution",
            "alerta": "CRITICAL",
            "confidence": 0.9,
            "timestamp": "2026-07-01T10:05:00",
        },
    ]
    v = build_verdict(issues)
    assert "timeline" in v
    assert isinstance(v["timeline"], list)
    assert len(v["timeline"]) >= 1
    blob = " ".join(str(x) for x in v["timeline"]).lower()
    assert "integrity" in blob or "prefetch" in blob or "bam" in blob
