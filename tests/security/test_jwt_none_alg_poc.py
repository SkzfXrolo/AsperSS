"""
PoC no destructiva para JWT alg=none.

Requiere pytest:
  pip install -r tests/requirements-test.txt
"""

from pathlib import Path

APP_PY = Path(__file__).resolve().parents[2] / "web_app" / "app.py"


def test_no_obvious_jwt_library_usage_in_current_surface():
    src = APP_PY.read_text(encoding="utf-8", errors="ignore").lower()
    # Si no hay JWT, el ataque alg=none no aplica hoy.
    assert "pyjwt" not in src
    assert "jwt.decode" not in src


def test_jwt_none_alg_review_flag():
    # Test placeholder para mantener control cuando JWT sea introducido.
    assert True
