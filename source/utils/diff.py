from __future__ import annotations


def _key(item: dict) -> tuple:
    return (
        str(item.get("tipo", "")),
        str(item.get("ruta", "")),
        str(item.get("archivo", "")),
        str(item.get("nombre", "")),
    )


def diff_scans(scan_a: dict, scan_b: dict) -> dict:
    """Compara dos resultados de scan y devuelve added/removed/changed."""
    issues_a = { _key(i): i for i in (scan_a.get("issues_found") or []) if isinstance(i, dict) }
    issues_b = { _key(i): i for i in (scan_b.get("issues_found") or []) if isinstance(i, dict) }

    keys_a = set(issues_a.keys())
    keys_b = set(issues_b.keys())

    added = [issues_b[k] for k in sorted(keys_b - keys_a)]
    removed = [issues_a[k] for k in sorted(keys_a - keys_b)]

    changed = []
    for k in sorted(keys_a & keys_b):
        a = issues_a[k]
        b = issues_b[k]
        if a != b:
            changed.append({"key": k, "before": a, "after": b})

    return {"added": added, "removed": removed, "changed": changed}
