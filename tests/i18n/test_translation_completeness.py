from __future__ import annotations


def test_translation_completeness_smoke():
    en = {"login": "Login", "logout": "Logout", "help": "Help"}
    es = {"login": "Iniciar sesión", "logout": "Cerrar sesión", "help": "Ayuda"}
    assert set(en.keys()) == set(es.keys())
