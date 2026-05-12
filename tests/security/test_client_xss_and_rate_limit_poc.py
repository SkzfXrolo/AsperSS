from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_PY = ROOT / "web_app" / "app.py"
PANEL_JS = ROOT / "web_app" / "static" / "js" / "panel.js"


def test_rate_limit_scope_is_too_narrow_poc():
    """
    PoC no destructiva:
    el limitador existe, pero su set de rutas públicas es mínimo y
    no cubre login/auth.
    """
    src = APP_PY.read_text(encoding="utf-8", errors="ignore")
    assert "PUBLIC_LIMITED = {'/api/submit', '/api/predict', '/api/scan/submit'}" in src
    assert "@app.route('/api/auth/login', methods=['POST'])" in src


def test_panel_innerhtml_uses_unescaped_fields_poc():
    """
    PoC no destructiva:
    detecta render HTML de campos dinámicos en historial de veredictos.
    """
    js = PANEL_JS.read_text(encoding="utf-8", errors="ignore")
    assert "panel.innerHTML = h.map(e =>" in js
    assert "${e.reason ||" in js
    assert "${e.changed_by}" in js
