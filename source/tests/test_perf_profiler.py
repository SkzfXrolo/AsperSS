from perf.profiler import ScannerProfiler


def test_profiler_records():
    p = ScannerProfiler()
    out = p.measure("x", lambda: 123)
    assert out == 123
    assert "x" in p.report()

