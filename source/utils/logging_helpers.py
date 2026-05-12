from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def configure_structured_logging(logger_name: str = "argus", level: int = logging.INFO, as_json: bool = False):
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        if as_json:
            handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger

