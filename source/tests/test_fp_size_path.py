"""P2 #8 size filter + P2 #14 path/name correlation."""
import os
import tempfile

from main import ArgusApp


def _app():
    return object.__new__(ArgusApp)


def test_tiny_jar_dropped():
    app = _app()
    with tempfile.TemporaryDirectory() as td:
        tiny = os.path.join(td, "noise.jar")
        with open(tiny, "wb") as f:
            f.write(b"PK" + b"\x00" * 100)
        issues = [{
            "tipo": "jar_file",
            "alerta": "CRITICAL",
            "confidence": 0.8,
            "ruta": tiny,
            "archivo": "noise.jar",
            "detected_patterns": [],
        }]
        out = ArgusApp._filter_by_file_size(app, issues)
        assert out == []


def test_generic_name_legit_path_demotes():
    app = _app()
    issues = [{
        "tipo": "suspicious_process",
        "alerta": "CRITICAL",
        "confidence": 0.8,
        "ruta": r"C:\Program Files\NVIDIA Corporation\update.exe",
        "archivo": "update.exe",
        "detected_patterns": [],
    }]
    out = ArgusApp._apply_process_path_correlation(app, issues)
    assert out[0]["alerta"] == "POCO_SOSPECHOSO"
    assert "path_name_legit_demote" in out[0]["detected_patterns"]


def test_process_whitelist_drops_discord_noise():
    app = _app()
    issues = [{
        "tipo": "suspicious_process",
        "categoria": "PROCESO",
        "alerta": "SOSPECHOSO",
        "confidence": 0.4,
        "archivo": "discord.exe",
        "ruta": r"C:\Users\x\AppData\Local\Discord\discord.exe",
    }]
    out = ArgusApp._apply_process_whitelist(app, issues)
    assert out == []
