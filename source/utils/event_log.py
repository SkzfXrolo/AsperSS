from __future__ import annotations

import subprocess


class EventLogReader:
    def _read_log(self, log_name, event_id=None, provider=None, max_events=100):
        q = "*"
        if event_id is not None:
            q = f"*[System[(EventID={int(event_id)})]]"
        cmd = ["wevtutil", "qe", log_name, f"/q:{q}", f"/c:{int(max_events)}", "/rd:true", "/f:text"]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=15, creationflags=0x08000000)
            out = (r.stdout or b"").decode("utf-8", errors="ignore")
        except Exception:
            out = ""
        if provider:
            out = "\n".join([ln for ln in out.splitlines() if provider.lower() in ln.lower()])
        return out

    def read_security_log(self, filter=None):
        filter = filter or {}
        return self._read_log("Security", event_id=filter.get("event_id"), provider=filter.get("source"), max_events=filter.get("max_events", 100))

    def read_system_log(self, filter=None):
        filter = filter or {}
        return self._read_log("System", event_id=filter.get("event_id"), provider=filter.get("source"), max_events=filter.get("max_events", 100))

    def read_application_log(self, filter=None):
        filter = filter or {}
        return self._read_log("Application", event_id=filter.get("event_id"), provider=filter.get("source"), max_events=filter.get("max_events", 100))

