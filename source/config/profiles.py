from __future__ import annotations


PROFILES = {
    "quick": {"threads": 2, "timeout_sec": 10},
    "full": {"threads": 4, "timeout_sec": 20},
    "paranoid": {"threads": 6, "timeout_sec": 40},
}


def get_profile(name: str):
    return dict(PROFILES.get(name, PROFILES["full"]))

