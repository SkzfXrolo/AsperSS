"""
PoC estática no destructiva para superficie IDOR.

Requiere pytest:
  pip install -r tests/requirements-test.txt
"""

from pathlib import Path
import re

APP_PY = Path(__file__).resolve().parents[2] / "web_app" / "app.py"


def test_idor_surface_with_int_identifiers():
    src = APP_PY.read_text(encoding="utf-8", errors="ignore")
    routes = re.findall(r"@app\.route\('/api/[^']*<int:[^>]+>[^']*'", src)
    assert routes, "No se detectaron rutas con IDs enteros."


def test_company_scoped_routes_exist_for_review():
    src = APP_PY.read_text(encoding="utf-8", errors="ignore")
    assert "/api/company/users/<int:user_id>" in src or "/api/scans/<int:scan_id>" in src
