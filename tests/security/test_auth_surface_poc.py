from pathlib import Path


APP_PY = Path(__file__).resolve().parents[2] / "web_app" / "app.py"


def _source() -> str:
    return APP_PY.read_text(encoding="utf-8", errors="ignore")


def test_public_bootstrap_admin_route_present_poc():
    """
    PoC no destructiva:
    valida que existe un endpoint de setup admin por GET.
    """
    src = _source()
    assert "@app.route('/setup-admin-aspers2024', methods=['GET'])" in src
    assert "def setup_admin():" in src


def test_superadmin_hardcoded_fallback_present_poc():
    """
    PoC no destructiva:
    detecta fallback de credenciales superadmin hardcodeadas.
    """
    src = _source()
    assert "SUPER_ADMIN_USER" in src and "Rodrigo" in src
    assert "SUPER_ADMIN_PASS" in src and "Rodrigo@1" in src
