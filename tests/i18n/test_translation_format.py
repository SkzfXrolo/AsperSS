from __future__ import annotations

import re


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{([a-zA-Z0-9_]+)\}", text))


def test_translation_placeholders_match():
    en = "Player {player} got {count} warnings"
    es = "El jugador {player} recibió {count} advertencias"
    assert placeholders(en) == placeholders(es)
