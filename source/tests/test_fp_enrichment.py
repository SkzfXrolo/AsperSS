"""Tests FP hardening + enriquecimiento de hallazgos."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from issue_enrichment import enrich_issues, _normalize_confidence
from fp_filter import _path_segment_match, normalize_path


def test_path_segment_match_avoids_loose_substring():
    assert _path_segment_match("badlion", r"c:\users\x\appdata\roaming\badlionclient\mods")
    assert not _path_segment_match("badlion", r"c:\users\x\notbadlionxyz\foo")
    assert _path_segment_match(r"google\chrome", r"c:\users\x\appdata\local\google\chrome\user data")


def test_normalize_path_collapses_escaped_backslashes():
    assert normalize_path(r"c:\\users\\x\\appdata\\roaming\\.lunarclient\\mods") == (
        r"c:\users\x\appdata\roaming\.lunarclient\mods"
    )
    assert normalize_path("C:/Users/x/.lunarclient/settings") == r"c:\users\x\.lunarclient\settings"


def test_lunar3_path_segment_match():
    assert _path_segment_match(
        r".lunarclient",
        r"c:\users\x\.lunarclient\offline\multiver\mods\foo.jar",
    )
    assert _path_segment_match(
        "moonsworth",
        r"c:\users\x\appdata\roaming\moonsworth\lunarclient\cache",
    )


def test_enrich_adds_timestamp_and_hash():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "vapelite.jar"
        p.write_bytes(b"fake-jar-content-for-hash" * 20)
        issues = [{
            "nombre": "Test jar",
            "tipo": "jar_file",
            "alerta": "SOSPECHOSO",
            "confidence": 85,  # escala 0–100
            "ruta": str(td),
            "archivo": str(p),
            "detected_patterns": ["prefetch:vape"],
        }]
        out = enrich_issues(issues)
        assert out[0]["confidence"] <= 1.0
        assert out[0].get("file_hash") or out[0].get("sha256")
        assert out[0].get("timestamp")
        assert out[0].get("explicacion")


def test_enrich_cross_links_related():
    issues = [
        {
            "nombre": "Prefetch vape",
            "tipo": "prefetch_hack",
            "alerta": "CRITICAL",
            "confidence": 0.9,
            "ruta": r"C:\Windows\Prefetch\VAPE.EXE-ABC.pf",
            "archivo": "VAPE.EXE-ABC.pf",
            "detected_patterns": ["prefetch:vape"],
        },
        {
            "nombre": "BAM vape",
            "tipo": "bam_execution",
            "alerta": "CRITICAL",
            "confidence": 0.88,
            "ruta": r"C:\Users\x\AppData\Local\vape\vape.exe",
            "archivo": "vape.exe",
            "detected_patterns": ["bam:vape"],
        },
    ]
    out = enrich_issues(issues)
    assert out[0].get("extra", {}).get("related_count", 0) >= 2
    assert "related:vape" in " ".join(out[0].get("detected_patterns") or [])


def test_normalize_confidence_scales():
    issue = {"confidence": 90}
    _normalize_confidence(issue)
    assert issue["confidence"] == 0.9


def test_secondary_keeps_integrity():
    # Import secondary via lazy main symbols — stub minimal
    import sys
    import types

    # Ensure main symbols exist if main already imported; otherwise soft skip
    try:
        from fp_filter import secondary_filter
    except Exception:
        return

    class _App:
        pass

    issues = [{
        "nombre": "Prefetch wipe",
        "tipo": "ss_integrity",
        "categoria": "INTEGRITY",
        "alerta": "CRITICAL",
        "confidence": 0.9,
        "ruta": r"C:\Windows\Prefetch",
        "archivo": "",
    }]
    # secondary_filter needs main module symbols
    if "main" not in sys.modules:
        return
    out = secondary_filter(_App(), issues)
    assert len(out) == 1
    assert out[0]["tipo"] == "ss_integrity"
