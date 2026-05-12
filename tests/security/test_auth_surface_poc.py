from pathlib import Path

import pytest


APP_PY = Path(__file__).resolve().parents[2] / "web_app" / "app.py"


def _source() -> str:
    return APP_PY.read_text(encoding="utf-8", errors="ignore")


@pytest.mark.xfail(reason="Pack49: security hardening removió bootstrap/hardcoded path", strict=False)
def test_public_bootstrap_admin_route_present_poc():
    """
    PoC no destructiva:
    valida que existe un endpoint de setup admin por GET.
    """
    src = _source()
    assert "@app.route('/setup-admin-aspers2024', methods=['GET'])" in src
    assert "def setup_admin():" in src


@pytest.mark.xfail(reason="Pack49: drift de seguridad, fallback hardcoded eliminado", strict=False)
def test_superadmin_hardcoded_fallback_present_poc():
    """
    PoC no destructiva:
    detecta fallback de credenciales superadmin hardcodeadas.
    """
    src = _source()
    assert "SUPER_ADMIN_USER" in src and "Rodrigo" in src
    assert "SUPER_ADMIN_PASS" in src and "Rodrigo@1" in src
