"""Garantiza que el pipeline no llame métodos inexistentes."""
import inspect
import re

import main
from scan_pipeline import ScanPipeline


def _quoted_callable_names(src: str):
    return re.findall(r'"(?:scan_|advanced_)[a-z0-9_]+"', src)


def test_all_pipeline_scan_methods_exist():
    src = inspect.getsource(ScanPipeline)
    names = {n.strip('"') for n in _quoted_callable_names(src)}
    assert names, "no scan_* found in pipeline"
    missing = sorted(n for n in names if not hasattr(main.ArgusApp, n))
    assert missing == [], f"pipeline calls missing methods: {missing}"


def test_prefetch_uses_real_method():
    src = inspect.getsource(ScanPipeline._bind_handlers)
    assert "scan_prefetch_hacks" in src
    assert "scan_prefetch_hack_executions" not in src
    assert "advanced_minecraft_process_analysis" in src
    assert "scan_minecraft_process_info" not in src
