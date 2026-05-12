from __future__ import annotations

import time
from contextlib import contextmanager


@contextmanager
def timer():
    start = time.perf_counter()
    data = {"elapsed": 0.0}
    try:
        yield data
    finally:
        data["elapsed"] = time.perf_counter() - start

