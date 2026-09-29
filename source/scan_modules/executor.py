"""
Ejecutor paralelo de módulos extendidos (70) + minado (3).
Respeta scanner_custom.json (beta) para activar/desactivar módulos.
"""
import concurrent.futures
import time

try:
    from config.scanner_custom import load_scanner_custom, is_module_enabled
except ImportError:
    def load_scanner_custom():
        return {}
    def is_module_enabled(_c, _id, default=True):
        return default

from scan_modules.context import ScanContext
from scan_modules.novel_surfaces import NOVEL_MODULES
from scan_modules import mining_automation as mining

try:
    from scan_modules.extended_checks import EXTENDED_MODULES
except Exception:
    EXTENDED_MODULES = []

MINING_MODULES = [
    ('mine_001', 'Baritone traces', mining.scan_baritone_traces),
    ('mine_002', 'Auto-mine macros', mining.scan_auto_mine_macros),
    ('mine_003', 'Mining bot processes', mining.scan_mining_bot_processes),
]


def _all_modules():
    # extended_checks cableados (v1.8); default enabled=False en Standard vía scanner_custom
    return list(NOVEL_MODULES) + list(EXTENDED_MODULES) + list(MINING_MODULES)


def run_pack_modules(app, progress_cb=None):
    """
    Ejecuta módulos habilitados. progress_cb(phase_text) opcional.
    Devuelve lista agregada de hallazgos.
    """
    ctx = ScanContext(app)
    app._scan_ctx = ctx
    custom = load_scanner_custom()
    perf = custom.get('performance') or {}
    pool_size = int(perf.get('module_pool_size') or 6)
    timeout = float(perf.get('module_default_timeout_sec') or 10)
    # ext_* ruidosos: OFF en Standard; ON en Paranoid (salvo override en scanner_custom)
    paranoid = str(getattr(app, 'scan_mode', '') or '').lower() == 'paranoid'
    enabled = [
        m for m in _all_modules()
        if is_module_enabled(
            custom, m[0],
            default=(True if paranoid else (not str(m[0]).startswith('ext_'))),
        )
    ]
    if not enabled:
        return []

    findings = []
    t0 = time.time()
    print(f"[PACK v1.7] Ejecutando {len(enabled)} módulos nuevos (pool={pool_size}, timeout={timeout}s)…")

    def _run_one(spec):
        mod_id, label, fn = spec
        try:
            t1 = time.time()
            res = fn(ctx) or []
            dt = time.time() - t1
            if res:
                print(f"[PACK] {mod_id} ({label}): {len(res)} hallazgo(s) en {dt:.2f}s")
            return res
        except Exception as e:
            print(f"[PACK] {mod_id} error: {e}")
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as ex:
        futures = {ex.submit(_run_one, spec): spec[0] for spec in enabled}
        for fut in concurrent.futures.as_completed(futures, timeout=max(timeout * len(enabled), 120)):
            mod_id = futures[fut]
            try:
                findings.extend(fut.result(timeout=timeout))
            except concurrent.futures.TimeoutError:
                print(f"[PACK] {mod_id} timeout ({timeout}s)")
            except Exception as e:
                print(f"[PACK] {mod_id} falló: {e}")
            if progress_cb:
                try:
                    progress_cb(f"Módulos extendidos… ({len(findings)} hallazgos)")
                except Exception:
                    pass

    print(f"[PACK v1.7] Listo: {len(findings)} hallazgos en {time.time() - t0:.1f}s")
    return findings
