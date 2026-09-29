"""Smoke: fases Fast incluyen checks P1 que antes solo corrían en legacy."""
from scan_pipeline import MODE_FAST, MODE_STANDARD, phases_for_mode, ScanPipeline


class _DummyApp:
    issues_found = []

    def _scan_cancelled(self):
        return False


def test_fast_phases_include_high_value_and_autoclickers():
    phases = phases_for_mode(MODE_FAST)
    assert "processes" in phases
    assert "autoclickers" in phases
    assert "high_value" in phases
    assert "evasion" in phases
    assert "complements" in phases


def test_pipeline_binds_p1_methods():
    p = ScanPipeline(_DummyApp(), mode=MODE_FAST)
    # handlers existen
    assert "processes" in p._handlers
    assert "autoclickers" in p._handlers
    assert "high_value" in p._handlers
    assert "evasion" in p._handlers
    assert "complements" in p._handlers


def test_standard_has_forensics_pack():
    phases = phases_for_mode(MODE_STANDARD)
    assert "forensics_pack" in phases
    assert "registry_exec" in phases
    assert "browser" in phases
    assert "memory_strings" in phases


def test_evasion_runs_vpn_hosts_dns():
    import inspect
    src = inspect.getsource(ScanPipeline._run_evasion)
    for name in ("scan_vpn_adapters", "scan_hosts_file", "scan_dns_cache", "scan_evasion_indicators"):
        assert name in src
