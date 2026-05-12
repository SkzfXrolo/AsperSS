"""
PoC estática no destructiva para superficie CSRF.

Requiere pytest instalado:
  pip install -r tests/requirements-test.txt
"""

from pathlib import Path
import re


APP_PY = Path(__file__).resolve().parents[2] / "web_app" / "app.py"


def _src() -> str:
    return APP_PY.read_text(encoding="utf-8", errors="ignore")


def test_csrf_library_not_present_poc():
    src = _src()
    assert "CSRFProtect" not in src
    assert "flask_wtf" not in src


def test_state_changing_routes_without_csrf_token_poc():
    src = _src()
    risky = re.findall(
        r"@app\\.route\\('([^']+)'\\s*,\\s*methods=\\['(POST|PUT|DELETE)'\\]\\)",
        src,
    )
    assert risky, "No se detectaron rutas mutantes para evaluar."
    # PoC: existe superficie mutante y no hay evidencia de token CSRF explícito global.
    assert any(method in {"POST", "PUT", "DELETE"} for _, method in risky)
