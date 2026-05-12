from __future__ import annotations

import csv
import io


def export_timeline_csv(events: list[dict]) -> str:
    ordered = sorted(events or [], key=lambda e: str(e.get("timestamp", "")))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["timestamp", "type", "detail"])
    w.writeheader()
    for e in ordered:
        w.writerow({"timestamp": e.get("timestamp", ""), "type": e.get("type", ""), "detail": e.get("detail", "")})
    return buf.getvalue()

