from __future__ import annotations

"""Perfiles de scan v1.8 — Fast / Standard / Paranoid vía ScanPipeline."""

try:
    from scan_pipeline import (
        MODE_FAST,
        MODE_STANDARD,
        MODE_PARANOID,
        normalize_mode,
        profile_dict,
        phases_for_mode,
        eta_for_mode,
    )
except ImportError:  # pragma: no cover
    MODE_FAST, MODE_STANDARD, MODE_PARANOID = "fast", "standard", "paranoid"

    def normalize_mode(name: str):
        return (name or "standard").lower()

    def profile_dict(mode: str):
        return {"name": mode, "threads": 4, "timeout_sec": 20, "eta_sec": 540, "phases": []}

    def phases_for_mode(mode: str):
        return []

    def eta_for_mode(mode: str):
        return 540


PROFILES = {
    "quick": profile_dict(MODE_FAST),
    "fast": profile_dict(MODE_FAST),
    "full": profile_dict(MODE_STANDARD),
    "standard": profile_dict(MODE_STANDARD),
    "paranoid": profile_dict(MODE_PARANOID),
}


def get_profile(name: str):
    mode = normalize_mode(name)
    return profile_dict(mode)

