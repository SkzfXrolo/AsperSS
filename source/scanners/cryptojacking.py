from __future__ import annotations

import psutil


MINER_NAMES = ("xmrig", "cpuminer", "miner", "ethminer")

# Pseudo-procesos del kernel de Windows — nunca son "un proceso que consume
# CPU minando", psutil.cpu_percent() sin calibrar (ver abajo) les puede dar
# valores absurdos (ej. "System Idle Process" con >900%).
_OS_PSEUDO_PROCESSES = ("system idle process", "system", "registry",
                        "memory compression", "secure system")


def scan_cryptojacking(cpu_threshold=70.0):
    findings = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "exe"]):
        try:
            name = (p.info.get("name") or "").lower()
            if name in _OS_PSEUDO_PROCESSES:
                continue
            cpu = float(p.info.get("cpu_percent") or 0.0)
            # cpu_percent() en el primer sample de process_iter no está
            # calibrado contra un intervalo real (compara contra el arranque
            # del proceso) — valores >100% en un solo core son ruido de
            # medición, no evidencia de minería.
            if cpu > 100.0:
                continue
            if any(m in name for m in MINER_NAMES) or cpu >= cpu_threshold:
                findings.append({"pid": p.info["pid"], "name": name, "cpu": cpu, "exe": p.info.get("exe", "")})
        except Exception:
            continue
    return findings

