"""
SS Verdict Engine — lo que Echo dumpa como strings y Ocean resume como risk score,
Argus lo convierte en un veredicto con kill-chain.

Filosofía:
- Preferir precisión a "detectar más"
- Un CRITICAL aislado de baja confianza ≠ ban
- Varias señales correlacionadas (ejecución + integridad + cliente) = CHEATER
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


VERDICT_CLEAN = "CLEAN"
VERDICT_SUSPICIOUS = "SUSPICIOUS"
VERDICT_LIKELY = "LIKELY_CHEATER"
VERDICT_CONFIRMED = "CONFIRMED_CHEATER"

_GHOST = (
    "vape", "vapelite", "sigma", "liquidbounce", "wurst", "rise", "flux",
    "future", "astolfo", "novoline", "drip", "entropy", "whiteout",
    "exhibition", "meteor", "rusherhack", "aristois", "tenacity", "konas",
    "inertia", "salhack", "ghost", "weave", "raven", "fdp", "nextgen",
)

_EXEC_TYPES = {
    "prefetch_hack", "prefetch_jna", "amcache_hack_execution", "amcache",
    "registry_userassist_hack", "shimcache", "appcompat_shimcache",
    "shimcache_suspicious", "usn_deleted_hack", "usn_ghost_folder",
    "bam", "bam_suspicious", "bam_execution", "bam_hack", "srum",
    "userassist_suspicious", "jump_list_suspicious",
    "muicache_suspicious", "typed_path_suspicious", "pca_telemetry_suspicious",
    "recent_docs_registry", "run_mru_suspicious", "recent_lnk_hack",
    "recent_lnk_suspicious", "windows_search_hack",
}

_INTEGRITY_TYPES = {
    "ss_integrity", "evasion_indicators", "eventlog_cleared_security_1102",
    "eventlog_cleared_system_104", "minecraft_safe_mode", "hosts_minecraft_redirect",
    "prescan_cleanup", "rdp_session_active",
    "lolbins_extra_suspicious", "security_4688_suspicious",
    "sysmon_operational_suspicious", "deleted_mass_event",
    "hosts_hack_distro",
}

_INJECT_TYPES = {
    "dll_injection", "dll_injection_java", "process_memory", "memory_strings",
    "java_cmdline", "injector", "injector_process", "manual_map",
    "javaagent_injection", "jdwp_debug_port", "hack_string_in_loaded_jar",
    "jar_self_deleted", "process_memory_keyword",
}

_CLIENT_TYPES = {
    "minecraft_jar", "jar_hack", "mod_jar", "weave_loader", "fabric_mod",
    "ghost_client_config", "ghost_client_registry", "blacklisted_mod",
    "jar_missing_mod_metadata", "temp_hack_binary", "recycle_hack",
    "recycle_hash_match", "lunar_unofficial_module", "python_hack_script",
    "exploit_process", "exploit_file",
}

_PERSIST_TYPES = {
    "scheduled_task_suspicious", "scheduled_task_args_suspicious",
    "scheduled_task_recent", "com_hijack_candidate", "registry_run_persistence",
    "wmi_event_subscription", "startup_entry_hack", "startup_hack_launcher",
}


def build_verdict(issues: list[dict], mouse_findings: list | None = None) -> dict[str, Any]:
    issues = list(issues or [])
    mouse_findings = list(mouse_findings or [])

    buckets = _bucket(issues)
    score = 0
    reasons: list[str] = []
    kill_chain: list[dict[str, str]] = []

    # --- Señales primarias ---
    crit = [i for i in issues if _alerta(i) == "CRITICAL"]
    susp = [i for i in issues if _alerta(i) == "SOSPECHOSO"]
    high_conf_crit = [i for i in crit if _conf(i) >= 0.85]

    # Ghost client nombrado
    ghosts = _match_ghosts(issues)
    if ghosts:
        score += 28 + min(20, 8 * (len(ghosts) - 1))
        reasons.append(f"Hack client(s): {', '.join(sorted(ghosts)[:5])}")
        kill_chain.append({"phase": "client", "detail": ", ".join(sorted(ghosts)[:5])})

    # Ejecución forense (Prefetch/BAM/Amcache/USN)
    exec_hits = buckets["execution"]
    if exec_hits:
        score += min(30, 10 + 4 * len(exec_hits))
        reasons.append(f"Evidencia de ejecución ({len(exec_hits)} artefactos)")
        kill_chain.append({
            "phase": "execution",
            "detail": exec_hits[0].get("nombre", "prefetch/bam/amcache")[:80],
        })

    # Integridad rota (Ocean: señal primaria — peso mayor en v1.8)
    integ = buckets["integrity"]
    if integ:
        # CRITICAL integrity hits weigh more (Prefetch wipe, EventLog, PS bypass)
        integ_crit = sum(1 for i in integ if _alerta(i) == "CRITICAL")
        score += min(45, 18 + 7 * len(integ) + 5 * integ_crit)
        top = integ[0].get("nombre", "integridad rota")
        reasons.append(f"Integridad rota: {top[:70]}")
        kill_chain.append({"phase": "integrity", "detail": top[:80]})
        if integ_crit:
            reasons.append(f"{integ_crit} bypass CRITICAL de integridad")

    # Inyección / memoria
    inj = buckets["injection"]
    if inj:
        score += min(25, 12 + 4 * len(inj))
        reasons.append(f"Inyección/memoria ({len(inj)})")
        kill_chain.append({"phase": "injection", "detail": inj[0].get("nombre", "")[:80]})

    # JARs / mods
    jars = buckets["client_files"]
    if jars:
        score += min(20, 8 + 3 * len(jars))
        reasons.append(f"JARs/mods sospechosos ({len(jars)})")
        kill_chain.append({"phase": "files", "detail": jars[0].get("nombre", "")[:80]})

    # Persistencia (tareas / COM / Run)
    persist = buckets["persistence"]
    if persist:
        score += min(22, 10 + 4 * len(persist))
        reasons.append(f"Persistencia sospechosa ({len(persist)})")
        kill_chain.append({
            "phase": "persistence",
            "detail": persist[0].get("nombre", "")[:80],
        })

    # Mouse / autoclick (silencioso)
    if mouse_findings:
        score += min(15, 5 * len(mouse_findings))
        reasons.append(f"Mouse/autoclick ({len(mouse_findings)})")
        kill_chain.append({"phase": "input", "detail": "anomalías de clic"})

    # CRITICAL de alta confianza
    if high_conf_crit:
        score += min(25, 8 * len(high_conf_crit))
        if not any("CRITICAL" in r for r in reasons):
            reasons.append(f"{len(high_conf_crit)} CRITICAL alta confianza")

    # Correlación kill-chain (múltiples fases)
    phases = {k["phase"] for k in kill_chain}
    if len(phases) >= 3:
        score += 18
        reasons.append(f"Kill-chain completa ({len(phases)} fases)")
    elif len(phases) == 2 and "integrity" in phases:
        score += 10
        reasons.append("Ejecución + integridad rotas")

    # Combos multi-evidencia (combination_penalty) — peso staff
    combos = {
        i.get("combination_penalty")
        for i in issues
        if i.get("combination_penalty")
    }
    if combos:
        score += min(22, 8 + 5 * len(combos))
        reasons.append(f"Combos evidencia: {', '.join(sorted(str(c) for c in combos)[:3])}")
        kill_chain.append({
            "phase": "correlation",
            "detail": ", ".join(sorted(str(c) for c in combos)[:4]),
        })

    # Penalización: solo LOW/NORMAL sin CRITICAL → no inflar
    if not crit and not susp and score < 20:
        score = min(score, 12)

    score = max(0, min(100, int(score)))
    verdict = _score_to_verdict(score, high_conf_crit, ghosts, phases, integ)

    timeline = _build_timeline(issues)

    return {
        "verdict": verdict,
        "risk_score": score,
        "reasons": reasons[:8],
        "kill_chain": kill_chain[:8],
        "timeline": timeline[:25],
        "counts": {
            "critical": len(crit),
            "suspicious": len(susp),
            "total": len(issues),
            "ghost_clients": len(ghosts),
            "integrity": len(integ),
            "execution": len(exec_hits),
        },
        "summary_es": _summary_es(verdict, score, reasons),
        "staff_action": _staff_action(verdict),
    }


def verdict_issue(verdict_data: dict) -> dict:
    """Hallazgo sintético para el panel / Discord."""
    v = verdict_data.get("verdict", VERDICT_CLEAN)
    alerta = {
        VERDICT_CLEAN: "NORMAL",
        VERDICT_SUSPICIOUS: "SOSPECHOSO",
        VERDICT_LIKELY: "SOSPECHOSO",
        VERDICT_CONFIRMED: "CRITICAL",
    }.get(v, "SOSPECHOSO")
    reasons = verdict_data.get("reasons") or []
    return {
        "nombre": f"VEREDICTO ARGUS: {v} (risk {verdict_data.get('risk_score', 0)}/100)",
        "ruta": "",
        "archivo": "",
        "tipo": "ss_verdict",
        "categoria": "VERDICT",
        "alerta": alerta,
        "confidence": min(0.99, 0.55 + (verdict_data.get("risk_score", 0) / 200.0)),
        "detected_patterns": [f"verdict:{v}", f"risk:{verdict_data.get('risk_score', 0)}"],
        "explicacion": verdict_data.get("summary_es", "")
        + ((" | " + " · ".join(reasons[:4])) if reasons else ""),
        "verdict_data": verdict_data,
    }


def _alerta(i: dict) -> str:
    return (i.get("alerta") or "").upper()


def _conf(i: dict) -> float:
    c = i.get("confidence")
    try:
        c = float(c or 0)
    except (TypeError, ValueError):
        return 0.0
    return c if c <= 1.0 else c / 100.0


def _bucket(issues: list[dict]) -> dict[str, list]:
    b = defaultdict(list)
    for i in issues:
        tipo = (i.get("tipo") or "").lower()
        cat = (i.get("categoria") or "").upper()
        text = (i.get("nombre", "") + " " + i.get("ruta", "")).lower()

        if tipo in _INTEGRITY_TYPES or cat == "INTEGRITY" or "integrity:" in str(i.get("detected_patterns")):
            b["integrity"].append(i)
        elif tipo in _EXEC_TYPES or "prefetch" in tipo or "amcache" in tipo or "bam" in tipo:
            b["execution"].append(i)
        elif tipo in _INJECT_TYPES or "inject" in text or "memory" in tipo:
            b["injection"].append(i)
        elif tipo in _PERSIST_TYPES or "scheduled_task" in tipo or cat == "PERSISTENCIA":
            b["persistence"].append(i)
        elif tipo in _CLIENT_TYPES or ".jar" in text or "mod" in tipo:
            b["client_files"].append(i)
        else:
            b["other"].append(i)
    return b


def _match_ghosts(issues: list[dict]) -> set[str]:
    found = set()
    for i in issues:
        blob = (
            str(i.get("nombre", "")) + " " + str(i.get("ruta", "")) + " "
            + str(i.get("archivo", "")) + " " + str(i.get("detected_patterns", ""))
        ).lower()
        for g in _GHOST:
            if g in blob:
                found.add(g)
    return found


def _score_to_verdict(score, high_conf_crit, ghosts, phases, integ) -> str:
    if score >= 75 and (high_conf_crit or (ghosts and "execution" in phases)):
        return VERDICT_CONFIRMED
    if score >= 60 and (len(phases) >= 2 or ghosts or integ):
        return VERDICT_LIKELY
    if score >= 35 or high_conf_crit or integ:
        return VERDICT_SUSPICIOUS
    return VERDICT_CLEAN


def _build_timeline(issues: list[dict]) -> list[dict]:
    """Timeline staff: Prefetch/BAM/USN/Amcache/integridad primero (Echo-style)."""
    PRIORITY_TYPES = (
        "ss_integrity", "prefetch_hack", "usn_deleted_hack", "amcache_hack_execution",
        "bam", "appcompat_shimcache", "evasion_indicators", "yara_java",
    )
    events = []
    for i in issues:
        if (i.get("tipo") or "") == "ss_verdict":
            continue
        alerta = _alerta(i)
        tipo = (i.get("tipo") or "").lower()
        cat = (i.get("categoria") or "").upper()
        is_priority = (
            tipo in PRIORITY_TYPES
            or cat == "INTEGRITY"
            or "integrity:" in str(i.get("detected_patterns") or "")
            or alerta in ("CRITICAL", "SOSPECHOSO")
        )
        if not is_priority:
            continue
        ts = (
            i.get("timestamp")
            or i.get("last_executed")
            or i.get("mtime")
            or i.get("fecha")
            or ""
        )
        # Sort key: real timestamps first; priority types without ts still surface
        sort_key = str(ts) if ts else f"0-{tipo}"
        phase = "integrity" if cat == "INTEGRITY" or tipo == "ss_integrity" else (
            "execution" if tipo in _EXEC_TYPES or "prefetch" in tipo or "bam" in tipo else
            "files" if ".jar" in (i.get("archivo") or "").lower() else "signal"
        )
        events.append({
            "timestamp": str(ts) if ts else "",
            "alerta": alerta,
            "tipo": i.get("tipo", ""),
            "phase": phase,
            "detail": (i.get("nombre") or "")[:100],
            "_sort": sort_key,
        })
    events.sort(key=lambda e: e.get("_sort") or "", reverse=True)
    for e in events:
        e.pop("_sort", None)
    return events


def _summary_es(verdict: str, score: int, reasons: list[str]) -> str:
    base = {
        VERDICT_CLEAN: "Sin evidencia suficiente de cheat. Revisar manual solo si hay reportes externos.",
        VERDICT_SUSPICIOUS: "Hay señales de riesgo. Requiere revisión manual antes de sancionar.",
        VERDICT_LIKELY: "Patrón coherente con uso de cheats. Alta probabilidad — verificar top hallazgos.",
        VERDICT_CONFIRMED: "Kill-chain consistente con cheater. Evidencia múltiple correlacionada.",
    }.get(verdict, "")
    return f"{base} Risk {score}/100."


def _staff_action(verdict: str) -> str:
    return {
        VERDICT_CLEAN: "Liberar / no ban por scanner solo",
        VERDICT_SUSPICIOUS: "Manual review + preguntar por programas listados",
        VERDICT_LIKELY: "Ban probable tras confirmar 1-2 hallazgos CRITICAL",
        VERDICT_CONFIRMED: "Ban justificado con evidencia del veredicto",
    }.get(verdict, "Revisar")
