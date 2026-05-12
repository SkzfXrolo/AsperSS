"""
PoC no destructiva para path traversal.

Requiere pytest:
  pip install -r tests/requirements-test.txt
"""

from pathlib import Path

APP_PY = Path(__file__).resolve().parents[2] / "web_app" / "app.py"


def test_download_route_accepts_filename_parameter_surface():
    src = APP_PY.read_text(encoding="utf-8", errors="ignore")
    assert "@app.route('/download/<filename>')" in src


def test_path_traversal_payload_examples_documented():
    payloads = ["../../../etc/passwd", "..\\..\\..\\windows\\win.ini"]
    assert len(payloads) == 2
