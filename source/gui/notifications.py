from __future__ import annotations


def notify_user(title: str, message: str, enabled: bool = False):
    if not enabled:
        return {"sent": False}
    # Placeholder cross-platform notification behavior
    print(f"[NOTIFY] {title}: {message}")
    return {"sent": True}

