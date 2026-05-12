from __future__ import annotations

import re


_URL_RE = re.compile(r"https?://[^\s\"']+", re.IGNORECASE)
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def export_to_ioc_text(scan_data: dict) -> str:
    lines: list[str] = []
    seen = set()
    for issue in (scan_data.get("issues_found") or []):
        if not isinstance(issue, dict):
            continue
        for field in ("ruta", "archivo", "nombre"):
            value = str(issue.get(field, ""))
            if not value:
                continue
            for url in _URL_RE.findall(value):
                if ("url", url) not in seen:
                    seen.add(("url", url))
                    lines.append(f"URL,{url}")
            for ip in _IP_RE.findall(value):
                if ("ip", ip) not in seen:
                    seen.add(("ip", ip))
                    lines.append(f"IP,{ip}")
            if "\\" in value or "/" in value:
                if ("path", value) not in seen:
                    seen.add(("path", value))
                    lines.append(f"PATH,{value}")
    return "\n".join(lines)

