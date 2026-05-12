from __future__ import annotations
import json,time
t0=time.perf_counter(); time.sleep(0.12)
print(json.dumps({"benchmark":"chaos_recovery","recovery_s":round(time.perf_counter()-t0,3)},indent=2))
