"""_call_many_parallel (usado ahora tambien para el 'heavy' de _run_deep_proc):
todos los scanners aportan hallazgos aunque appendeen directo a issues_found
desde hilos worker, y uno que revienta no tumba al resto."""
import threading
import time

import scan_pipeline


class _FakeApp:
    def __init__(self):
        self.issues_found = []
        self._cancelled_flag = False

    def _scan_cancelled(self):
        return self._cancelled_flag

    # devuelve lista -> el pipeline hace extend
    def scan_returns_list(self):
        time.sleep(0.05)
        return [{"tipo": "a", "alerta": "SOSPECHOSO"}]

    # appendea directo desde el hilo worker
    def scan_appends_direct(self):
        time.sleep(0.05)
        self.issues_found.append({"tipo": "b", "alerta": "CRITICAL"})

    def scan_boom(self):
        raise RuntimeError("scanner roto")

    def scan_slow(self):
        # Nota: _call_many_parallel NO cancela un scanner colgado (el
        # ThreadPoolExecutor interno hace shutdown(wait=True)); solo garantiza
        # que su result (devuelto como lista) NO se cuente si superó el timeout,
        # y que no bloquee en serie a los otros workers.
        time.sleep(2)
        return [{"tipo": "late"}]


def test_parallel_collects_all_and_survives_errors(monkeypatch):
    monkeypatch.setenv("ARGUS_SCANNER_TIMEOUT", "1")
    app = _FakeApp()
    pipe = scan_pipeline.ScanPipeline(app, mode="standard")

    t0 = time.time()
    pipe._call_many_parallel(
        "scan_returns_list", "scan_appends_direct", "scan_boom",
        "scan_slow", "scan_returns_list",
        max_workers=3,
    )
    elapsed = time.time() - t0

    # scan_slow supera el timeout de 1s -> su result "late" se descarta.
    # los 3 rápidos (2 list + 1 append directo) sí entran; scan_boom aporta 0.
    tipos = sorted(i["tipo"] for i in app.issues_found)
    assert tipos == ["a", "a", "b"], tipos
    # los workers rápidos corren en paralelo, no en serie tras el lento
    assert elapsed < 6, f"batch demasiado lento: {elapsed:.1f}s"


if __name__ == "__main__":
    class _MP:
        def setenv(self, k, v):
            import os
            os.environ[k] = v
    test_parallel_collects_all_and_survives_errors(_MP())
    print("OK")
