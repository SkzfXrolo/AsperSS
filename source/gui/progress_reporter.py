from __future__ import annotations

import time


class ProgressReporter:
    def __init__(self, total: int = 100):
        self.total = max(1, int(total))
        self.current = 0
        self.started = time.time()

    def update(self, step: int = 1):
        self.current = min(self.total, self.current + int(step))
        return self.snapshot()

    def snapshot(self):
        pct = round((self.current / self.total) * 100.0, 2)
        return {"current": self.current, "total": self.total, "percent": pct, "elapsed_sec": round(time.time() - self.started, 2)}

