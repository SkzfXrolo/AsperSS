from __future__ import annotations

import psutil


def get_process_tree():
    tree = {}
    for p in psutil.process_iter(["pid", "ppid", "name"]):
        info = p.info
        tree.setdefault(info.get("ppid"), []).append(info)
    return tree


def find_orphans():
    procs = {p.info["pid"]: p.info for p in psutil.process_iter(["pid", "ppid", "name"])}
    orphans = []
    for pid, info in procs.items():
        ppid = info.get("ppid")
        if ppid and ppid not in procs and ppid != 4:
            orphans.append(info)
    return orphans


def find_unusual_ancestors(target_proc):
    unusual = []
    target = target_proc.lower()
    for p in psutil.process_iter(["pid", "ppid", "name"]):
        name = (p.info.get("name") or "").lower()
        if target not in name:
            continue
        try:
            parent = psutil.Process(p.info["ppid"])
            parent_name = (parent.name() or "").lower()
            if parent_name in ("winword.exe", "excel.exe", "outlook.exe", "wscript.exe"):
                unusual.append({"pid": p.info["pid"], "name": name, "parent": parent_name})
        except Exception:
            continue
    return unusual

