from __future__ import annotations

from perf.profiler import ScannerProfiler


def run_benchmark(scanner_map: dict[str, callable]):
    prof = ScannerProfiler()
    results = {}
    for name, fn in scanner_map.items():
        results[name] = prof.measure(name, fn)
    return {"results": results, "timings": prof.report()}

