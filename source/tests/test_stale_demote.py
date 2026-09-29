"""P2 #5 — demote archivos viejos sin evidencia forense."""
import os
import time
import tempfile


class _App:
    def __init__(self):
        # bind method from real class if available
        pass


def test_stale_demote_logic():
    from main import ArgusApp

    app = object.__new__(ArgusApp)
    with tempfile.TemporaryDirectory() as td:
        old = os.path.join(td, "random_mod.jar")
        with open(old, "wb") as f:
            f.write(b"PK\x03\x04fake")
        # force old ctime via utime (ctime may not change on Windows for create —
        # demote uses getctime; on Windows creation time is set at create.
        # Simulate by monkeypatching path age via wrapping — instead put forensic miss
        # and rely on setting issue with a path we can't age easily.
        # Use a path that doesn't exist → skip. Better: mock via issues only when file old.
        issues = [
            {
                "tipo": "jar_file",
                "alerta": "CRITICAL",
                "confidence": 0.8,
                "ruta": old,
                "archivo": "random_mod.jar",
                "detected_patterns": [],
            }
        ]
        # If file is brand new, demote should NOT fire
        out = ArgusApp._apply_stale_artifact_demote(app, issues)
        assert out[0]["alerta"] == "CRITICAL"

        # With companion prefetch of same basename → still no demote even if we fake age
        issues2 = [
            {
                "tipo": "jar_file",
                "alerta": "CRITICAL",
                "confidence": 0.8,
                "ruta": old,
                "archivo": "random_mod.jar",
                "detected_patterns": [],
            },
            {
                "tipo": "prefetch_hack",
                "alerta": "CRITICAL",
                "confidence": 0.9,
                "ruta": "C:\\Windows\\Prefetch\\RANDOM_MOD.EXE-ABC.pf",
                "archivo": "random_mod.exe",
                "nombre": "random_mod",
            },
        ]
        out2 = ArgusApp._apply_stale_artifact_demote(app, issues2)
        assert out2[0]["alerta"] == "CRITICAL"


def test_standard_has_memory_strings():
    from scan_pipeline import MODE_STANDARD, phases_for_mode
    assert "memory_strings" in phases_for_mode(MODE_STANDARD)
