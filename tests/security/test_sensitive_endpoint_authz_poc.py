"""
PoC estática no destructiva de authz en endpoints sensibles.

Requiere pytest instalado:
  pip install -r tests/requirements-test.txt
"""

from pathlib import Path


APP_PY = Path(__file__).resolve().parents[2] / "web_app" / "app.py"


def _src() -> str:
    return APP_PY.read_text(encoding="utf-8", errors="ignore")


def test_superadmin_area_exists_and_depends_on_session_poc():
    src = _src()
    assert "@app.route('/aspers-sa', methods=['GET', 'POST'])" in src
    assert "if not session.get('admin_subscriptions')" in src


def test_sensitive_debug_routes_not_login_protected_poc():
    src = _src()
    # PoC: rutas sensibles públicas detectadas para triage de hardening.
    assert "@app.route('/api/db-status', methods=['GET'])" in src
    assert "@app.route('/api/debug/last-scan')" in src
    assert "@app.route('/api/db-stats', methods=['GET'])" in src
