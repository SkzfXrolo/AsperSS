from __future__ import annotations

import concurrent.futures


def run_safe(fn, timeout=20):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return {"ok": True, "result": fut.result(timeout=timeout)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

