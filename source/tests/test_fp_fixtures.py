"""Fixtures de regresión FP + kill-chain forense + forensic_match."""
from __future__ import annotations

import json
from pathlib import Path

from forensic_match import match_hack_stem


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fp_regression.json"


def _load_cases():
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data["cases"]


def test_match_hack_stem_boundary():
    assert match_hack_stem("VAPE.EXE-ABC.pf") == "vape"
    assert match_hack_stem("liquidbounce-fabric.jar") == "liquidbounce"
    # ambiguo sin co-token
    assert match_hack_stem("RISE.EXE-ZZZ.pf") is None
    assert match_hack_stem("riseclient.exe") in ("rise", "riseclient")
    # no match Chrome noise
    assert match_hack_stem("chrome_child.dll") is None


def test_forensic_kill_chain_2of3():
    import main

    class App:
        pass

    app = App()
    issues = [
        {
            "nombre": "Prefetch vape",
            "tipo": "prefetch_hack",
            "alerta": "CRITICAL",
            "confidence": 0.9,
            "ruta": r"C:\Windows\Prefetch\VAPE.EXE-1.pf",
            "archivo": "VAPE.EXE-1.pf",
            "detected_patterns": ["prefetch:vape"],
        },
        {
            "nombre": "BAM vape",
            "tipo": "bam_suspicious",
            "alerta": "SOSPECHOSO",
            "confidence": 0.85,
            "ruta": r"\Device\HarddiskVolume3\Users\x\vape.exe",
            "archivo": "vape.exe",
            "detected_patterns": ["bam:vape"],
        },
    ]
    out = main.ArgusApp._apply_forensic_kill_chain(app, issues)
    assert any(i.get("tipo") == "kill_chain" for i in out)
    kc = next(i for i in out if i.get("tipo") == "kill_chain")
    assert "vape" in (kc.get("nombre") or "").lower()
    assert kc.get("extra", {}).get("related_count", 0) >= 2


def test_fp_fixture_cases():
    import main
    from fp_filter import filter_false_positives, secondary_filter

    class FakeApp:
        legitimate_patterns = None
        _cloud_hash_frequency = {}
        scan_mode = "standard"

        def _apply_remote_fp_rules(self, issues):
            return issues

        def _cached_sha256(self, *a, **k):
            return None

        def _mbaz_check_hash(self, *a, **k):
            return False

        def _vt_check_hash(self, *a, **k):
            return None

        def _get_active_launcher_instance_paths(self):
            return []

        def _get_abandoned_instance_paths(self):
            return []

        def _filter_by_file_size(self, x):
            return x

        def _filter_backup_sync(self, x):
            return x

        def _apply_score_decay(self, x):
            return x

        def _apply_feedback_thresholds(self, x):
            return x

        def _apply_human_explanations(self, x):
            return x

        def _group_related_results(self, x):
            return x

        def _apply_process_whitelist(self, x):
            return x

        def _apply_process_path_correlation(self, x):
            return x

        def _apply_legit_parent_demote(self, x):
            return x

        def _apply_authenticode_demote(self, x):
            return x

        def _apply_stale_artifact_demote(self, x):
            return x

        def _apply_long_uptime_demote(self, x):
            return x

        def _apply_badlion_informational(self, x):
            return x

        def _apply_cloud_rarity_and_ban_patterns(self, x):
            return x

        def _apply_single_indicator_cap(self, x):
            return main.ArgusApp._apply_single_indicator_cap(self, x)

        def _apply_combination_penalties(self, x):
            return x

        def _ai_contextual_boost(self, x):
            return x

    app = FakeApp()
    failures = []
    for case in _load_cases():
        issue = dict(case["issue"])
        via = case.get("via") or "filter"
        if via == "secondary":
            out = secondary_filter(app, [issue])
        else:
            out = filter_false_positives(app, [issue])
        expect = case["expect"]
        cid = case["id"]
        if expect == "drop":
            if len(out) != 0:
                failures.append(f"{cid}: expected drop, got {out}")
        elif expect == "keep":
            if len(out) != 1:
                failures.append(f"{cid}: expected keep, got {out}")
        elif expect == "soft_sospechoso":
            if len(out) != 1 or out[0].get("alerta") != "SOSPECHOSO":
                failures.append(f"{cid}: expected soft keep, got {out}")
        else:
            raise AssertionError(f"unknown expect {expect}")
    assert not failures, "FP regression cases failed:\n  " + "\n  ".join(failures)
