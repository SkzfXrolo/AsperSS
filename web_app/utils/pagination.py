from __future__ import annotations

import base64
import json
from typing import Any


class Paginator:
    @staticmethod
    def encode_cursor(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    @staticmethod
    def decode_cursor(cursor: str | None) -> dict[str, Any]:
        if not cursor:
            return {}
        try:
            raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}
