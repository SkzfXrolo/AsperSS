"""
PoC estática no destructiva para exposición de secretos en respuestas.

Requiere pytest instalado:
  pip install -r tests/requirements-test.txt
"""

from pathlib import Path

import pytest


APP_PY = Path(__file__).resolve().parents[2] / "web_app" / "app.py"


def _src() -> str:
    return APP_PY.read_text(encoding="utf-8", errors="ignore")


@pytest.mark.xfail(reason="Pack49: review secret cambió por hardening", strict=False)
def test_hardcoded_review_secret_present_poc():
    src = _src()
    assert "_REVIEW_SECRET" in src
    assert "aspers-claude-review-2026" in src


def test_masked_env_endpoint_still_exposes_sensitive_key_names_poc():
    src = _src()
    assert "env_masked" in src
    assert "SECRET_KEY" in src
    assert "SUPER_ADMIN_PASS" in src
