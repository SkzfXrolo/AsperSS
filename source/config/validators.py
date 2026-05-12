from __future__ import annotations


def validate_config(cfg: dict):
    errors = []
    if cfg.get("profile") not in ("quick", "full", "paranoid"):
        errors.append("profile inválido")
    if int(cfg.get("threads", 1)) < 1:
        errors.append("threads debe ser >= 1")
    if int(cfg.get("timeout_sec", 1)) < 1:
        errors.append("timeout_sec debe ser >= 1")
    return {"ok": not errors, "errors": errors}

