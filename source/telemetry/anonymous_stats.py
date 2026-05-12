from __future__ import annotations

import platform


def build_anonymous_stats(duration_sec: float, findings_count: int):
    return {
        "duration_sec": round(float(duration_sec), 3),
        "findings_count": int(findings_count),
        "os": platform.platform(),
    }

