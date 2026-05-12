from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = getattr(record, "request_id", None)
        uid = getattr(record, "user_id", None)
        if rid:
            payload["request_id"] = rid
        if uid:
            payload["user_id"] = uid
        return json.dumps(payload, ensure_ascii=False)
