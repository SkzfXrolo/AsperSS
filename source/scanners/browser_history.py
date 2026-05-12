from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import shutil


def _read_chromium_history(db_path, limit=200):
    if not os.path.isfile(db_path):
        return []
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    shutil.copy2(db_path, tmp.name)
    rows = []
    try:
        conn = sqlite3.connect(tmp.name)
        cur = conn.cursor()
        cur.execute(
            "SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT ?",
            (limit,),
        )
        for url, title, ts in cur.fetchall():
            rows.append({"url": url, "title": title, "last_visit_time": ts})
        conn.close()
    except Exception:
        pass
    finally:
        try:
            os.remove(tmp.name)
        except Exception:
            pass
    return rows


def scan_browser_history(days=7):
    _ = days
    local = os.environ.get("LOCALAPPDATA", "")
    roaming = os.environ.get("APPDATA", "")
    targets = {
        "chrome": os.path.join(local, "Google", "Chrome", "User Data", "Default", "History"),
        "edge": os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "History"),
        "firefox": os.path.join(roaming, "Mozilla", "Firefox", "Profiles"),
    }
    out = {"chrome": _read_chromium_history(targets["chrome"]), "edge": _read_chromium_history(targets["edge"]), "firefox": []}
    if os.path.isdir(targets["firefox"]):
        cutoff = time.time() - (days * 86400)
        for d in os.listdir(targets["firefox"]):
            fdb = os.path.join(targets["firefox"], d, "places.sqlite")
            if os.path.isfile(fdb) and os.path.getmtime(fdb) >= cutoff:
                out["firefox"].append({"profile": d, "db": fdb})
    return out

