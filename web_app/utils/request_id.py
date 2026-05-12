from __future__ import annotations

import contextvars
import uuid
from flask import request, g

current_request_id = contextvars.ContextVar("current_request_id", default="")


def bind_request_id():
    rid = (request.headers.get("X-Request-ID") or "").strip()
    if not rid:
        rid = uuid.uuid4().hex
    g.request_id = rid
    current_request_id.set(rid)
    return rid


def get_request_id() -> str:
    return current_request_id.get("") or ""
