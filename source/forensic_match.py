"""Matching de stems de hacks para Prefetch/USN/BAM/Amcache — boundary + ambiguos."""
from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

try:
    from config.hack_signatures import stem_in_filename, filename_is_definite_hack
except Exception:  # pragma: no cover
    def stem_in_filename(stem: str, name: str) -> bool:  # type: ignore
        return bool(stem) and stem in (name or "")

    def filename_is_definite_hack(name: str, extra_stems: Iterable[str] = ()) -> bool:  # type: ignore
        return False


# Stems fuertes (boundary)
_BASE_STRONG: Tuple[str, ...] = (
    "vape", "vapelite", "liquidbounce", "wurst", "wurstclient",
    "astolfo", "novoline", "entropy", "entropyclient", "whiteout", "exhibition",
    "meteorclient", "rusherhack", "aristois", "tenacity",
    "vertexclient", "inertiaclient", "salhack", "jelloclient",
    "daturamc", "remixclient", "pandoraclient", "azura",
    "kamiblue", "konas", "weepcraft", "zeroday", "nyxclient",
    "lucidclient", "weaveloader", "extremeinjector", "xenos",
    "ghostclient", "hackclient", "aimbot", "killaura", "baritone",
    "sigmaclient", "fluxclient", "futureclient", "riseclient",
    "impactclient", "dripclient", "phobos", "dllinjector", "bspoof",
    "cheatengine", "autoclicker",
    # catálogo firmas
    "doomsday", "fdpclient", "nightx", "ravenbplus", "rise6",
    "sigma5", "sigma6", "vialcraft", "exhibition", "whiteoutclient",
    "thunderhack", "liquidbounceplus", "meteorrejects", "myau",
    "mathax", "vapev4",
)


def _catalog_extra_stems() -> Tuple[str, ...]:
    try:
        from bundle_runtime import load_signature_catalog
        extra = load_signature_catalog().get("stems_extra") or []
        return tuple(str(s).lower() for s in extra if s)
    except Exception:
        return ()


STRONG_STEMS: Tuple[str, ...] = tuple(
    dict.fromkeys(list(_BASE_STRONG) + list(_catalog_extra_stems()))
)

# Ambiguos: boundary + co-token
AMBIGUOUS_STEMS: Tuple[str, ...] = (
    "sigma", "flux", "rise", "impact", "future", "meteor", "rusher",
    "remix", "lucid", "nyx", "injector", "scaffold", "drip", "vertex",
    "inertia", "jello", "pandora", "datura", "xray", "ghost", "macro",
    "cheat", "hack", "inject", "wolfram", "reflex", "freelook",
)

# Co-tokens de contexto. NO incluir stems ambiguos (ghost, hack, cheat, inject)
# aquí: 'ghost' en CO_TOKENS + 'ghost' en AMBIGUOUS_STEMS hace que "Ghost Recon"
# se auto-valide. 'minecraft' / 'lunarclient' etc. son contexto real.
CO_TOKENS: Tuple[str, ...] = (
    "client", "vape", "loader", "bypass", "killaura", "autoclick",
    ".minecraft", "minecraft", "lunarclient", "badlion", "clicker", "aura",
    "wurst", "liquidbounce",
)
# Rutas de juegos/apps legítimas: si el texto viene de acá, no es un cheat.
_LEGIT_GAME_DIRS: Tuple[str, ...] = (
    "steamapps", "steamlibrary", "\\steam\\", "epic games", "\\epicgames",
    "riot games", "ubisoft", "ea games", "\\origin games", "rockstar games",
    "\\program files\\", "gog galaxy", "\\battle.net",
)


def match_hack_stem(text: str, extra_strong: Sequence[str] = ()) -> Optional[str]:
    """
    Devuelve el stem matcheado o None.
    Prefiere definite_hack / strong boundary; ambiguos solo con co-token.
    """
    name = (text or "").lower()
    if not name:
        return None
    # Juegos/apps legítimas: "Ghost Recon", "Battlefield", etc. no son cheats.
    if any(g in name for g in _LEGIT_GAME_DIRS) and not filename_is_definite_hack(name):
        return None
    if filename_is_definite_hack(name):
        for s in STRONG_STEMS:
            if stem_in_filename(s, name):
                return s
        # definite but not in STRONG — return first NEVER-like hit via boundary
        for s in extra_strong:
            if stem_in_filename(s, name):
                return s
        return "definite_hack"

    for stem in STRONG_STEMS:
        if stem_in_filename(stem, name):
            return stem
    for stem in extra_strong:
        if stem_in_filename(stem, name):
            return stem

    for stem in AMBIGUOUS_STEMS:
        if not stem_in_filename(stem, name):
            continue
        # el co-token no puede ser el propio stem
        if any((t != stem) and (stem_in_filename(t, name) or t in name) for t in CO_TOKENS):
            return stem
    return None


def iso_from_epoch(ts: float) -> str:
    try:
        from datetime import datetime
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return ""


def iso_from_bam_ts(ts_str: str) -> str:
    """Convierte 'YYYY-MM-DD HH:MM:SS' de BAM a ISO-ish."""
    s = (ts_str or "").strip()
    if not s or s.lower().startswith("desconoc"):
        return ""
    try:
        from datetime import datetime
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return s.replace(" ", "T")
