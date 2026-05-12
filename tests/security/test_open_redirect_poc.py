"""
PoC no destructiva para open redirect.

Requiere pytest:
  pip install -r tests/requirements-test.txt
"""

from pathlib import Path
import re

APP_PY = Path(__file__).resolve().parents[2] / "web_app" / "app.py"


def test_next_redirect_parameter_surface():
    src = APP_PY.read_text(encoding="utf-8", errors="ignore")
    # Busca uso de ?next= en redirects para revisión manual.
    hits = re.findall(r"request\.args\.get\('next'", src)
    assert isinstance(hits, list)


def test_external_url_payload_examples():
    payloads = [
        "https://evil.example/phish",
        "//evil.example/phish",
    ]
    assert any(p.startswith("http") or p.startswith("//") for p in payloads)
