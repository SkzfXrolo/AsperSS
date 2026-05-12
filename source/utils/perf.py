from __future__ import annotations

import cProfile
import functools
import io
import pstats
import time


def measure_time(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[PERF] {func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper


def profile_function(func, *args, **kwargs) -> tuple[object, str]:
    profiler = cProfile.Profile()
    profiler.enable()
    result = func(*args, **kwargs)
    profiler.disable()
    s = io.StringIO()
    pstats.Stats(profiler, stream=s).sort_stats("cumulative").print_stats(30)
    return result, s.getvalue()


class ScanProfiler:
    def __init__(self):
        self.sections: dict[str, float] = {}

    def start(self, section: str):
        self.sections[section] = -time.perf_counter()

    def stop(self, section: str):
        if section in self.sections:
            self.sections[section] += time.perf_counter()

    def report(self) -> dict[str, float]:
        return {k: round(v, 6) for k, v in self.sections.items() if v >= 0}

