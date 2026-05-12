from __future__ import annotations

import time


class ScannerProfiler:
    def __init__(self):
        self.stats = {}

    def measure(self, name: str, fn, *args, **kwargs):
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        self.stats[name] = time.perf_counter() - start
        return result

    def report(self):
        return {k: round(v, 6) for k, v in self.stats.items()}

