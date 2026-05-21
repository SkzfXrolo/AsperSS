"""Firmas de hacks compartidas — evita imports circulares desde main.py."""
from __future__ import annotations

import re
from typing import Iterable, Optional

# Nombres que NUNCA deben auto-whitelistearse solo por estar en .minecraft/mods
NEVER_LEGITIMATE_STEMS: frozenset[str] = frozenset({
    'vape', 'vapelite', 'vapev4', 'vapev2', 'entropy', 'entropyclient',
    'whiteout', 'liquidbounce', 'wurst', 'wurstclient', 'impactclient',
    'sigmaclient', 'fluxclient', 'futureclient', 'meteorclient', 'meteor-client',
    'riseclient', 'rusherhack', 'aristois', 'horion', 'novoline', 'astolfo',
    'killaura', 'aimbot', 'triggerbot', 'baritone', 'weave', 'weaveloader',
    'dripclient', 'ghostclient', 'salhack', 'inertia', 'remix', 'jello',
    'datura', 'azura', 'vertex', 'thunderhack', 'reflexclient', 'rageclient',
    'horion', 'moonclient', 'phobos', 'tenacity', 'weepcraft', 'konas',
})

# Blacklist de mods por nombre de archivo (stems específicos, sin substrings genéricos)
BLACKLISTED_MOD_STEMS: tuple[str, ...] = (
    'baritone', 'horion', 'impactclient', 'wurst', 'wurstclient', 'aristois',
    'meteorclient', 'meteor-client', 'sigmaclient', 'sigma5', 'sigma6',
    'ares', 'salhack', 'entropy', 'entropyclient', 'remix', 'inertia',
    'liquidbounce', 'fluxclient', 'vape', 'vapelite', 'riseclient',
    'futureclient', 'astolfo', 'novoline', 'rusherhack',
    'dripclient', 'vertex', 'azura', 'jello', 'datura', 'mathias', 'weave',
    'weaveloader', 'xraymod', 'killaura', 'aimbot', 'scaffoldhack',
    'autoclicker', 'clickgui', 'horion', 'moonclient', 'phobos', 'tenacity',
    'konas', 'weepcraft', 'thunderhack',
)

# Solo como palabra/segmento completo (evita "cheatengine" vs "cheat" en "recheat")
BOUNDARY_ONLY_MOD_STEMS: tuple[str, ...] = ('cheat', 'inject', 'hacked')


def _boundary_pattern(stem: str) -> re.Pattern:
    esc = re.escape(stem.lower())
    return re.compile(
        rf'(?<![a-z0-9]){esc}(?![a-z0-9])',
        re.IGNORECASE,
    )


def stem_in_filename(stem: str, filename_lower: str) -> bool:
    """True si `stem` aparece como segmento en el nombre del archivo."""
    if not stem or not filename_lower:
        return False
    name = filename_lower.replace('.jar', '').replace('.disabled', '')
    return _boundary_pattern(stem).search(name) is not None


def filename_is_definite_hack(filename_lower: str, extra_stems: Iterable[str] = ()) -> bool:
    stems = NEVER_LEGITIMATE_STEMS.union(extra_stems)
    return any(stem_in_filename(s, filename_lower) for s in stems)


def mod_blacklist_match(filename_lower: str) -> Optional[str]:
    """Devuelve el stem que matcheó o None."""
    if not filename_lower:
        return None
    for stem in BLACKLISTED_MOD_STEMS:
        if stem_in_filename(stem, filename_lower):
            return stem
    for stem in BOUNDARY_ONLY_MOD_STEMS:
        if stem_in_filename(stem, filename_lower):
            return stem
    return None
