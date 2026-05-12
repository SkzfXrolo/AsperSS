"""Cache unificada: Redis opcional + fallback LRU en memoria."""
from __future__ import annotations

import functools
import json
import os
import time
from typing import Any, Callable

try:
    import redis  # type: ignore
except Exception:
    redis = None

try:
    from cachetools import LRUCache  # type: ignore
except Exception:
    LRUCache = None


class Cache:
    def __init__(self, maxsize: int = 1000):
        self._redis = None
        self._mem = LRUCache(maxsize=maxsize) if LRUCache else {}
        self._exp: dict[str, float] = {}
        redis_url = os.environ.get("REDIS_URL", "").strip()
        if redis_url and redis is not None:
            try:
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    def get(self, key: str) -> Any:
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                if raw is None:
                    return None
                return json.loads(raw)
            except Exception:
                pass
        exp = self._exp.get(key)
        if exp is not None and exp < time.time():
            self.delete(key)
            return None
        return self._mem.get(key)

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if self._redis is not None:
            try:
                self._redis.setex(key, int(ttl), json.dumps(value, ensure_ascii=False))
            except Exception:
                pass
        self._mem[key] = value
        self._exp[key] = time.time() + max(1, int(ttl))

    def delete(self, key: str) -> None:
        if self._redis is not None:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._mem.pop(key, None)
        self._exp.pop(key, None)

    def clear(self) -> None:
        if self._redis is not None:
            try:
                self._redis.flushdb()
            except Exception:
                pass
        self._mem.clear()
        self._exp.clear()


cache = Cache()


def cached(ttl: int = 300, key_prefix: str = "") -> Callable:
    def _decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def _wrap(*args, **kwargs):
            key = f"{key_prefix}:{fn.__name__}:{repr(args)}:{repr(sorted(kwargs.items()))}"
            hit = cache.get(key)
            if hit is not None:
                return hit
            out = fn(*args, **kwargs)
            cache.set(key, out, ttl=ttl)
            return out
        return _wrap
    return _decorator
