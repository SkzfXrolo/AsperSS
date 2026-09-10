"""Rankeo y render Top-N hallazgos para UI staff (resto colapsado)."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

_ALERT_SCORE = {
    "CRITICAL": 4,
    "MUY_SOSPECHOSO": 3,
    "SOSPECHOSO": 2,
    "POCO_SOSPECHOSO": 1,
    "NORMAL": 0,
}

_TYPE_BOOST = {
    "ss_verdict": 100,
    "ss_integrity": 50,
    "kill_chain": 45,
    "prefetch_hack": 30,
    "bam_suspicious": 28,
    "usn_deleted_hack": 26,
    "usn_ghost_folder": 28,
    "hack_string_in_loaded_jar": 27,
    "short_lived_process": 25,
    "jar_missing_mod_metadata": 22,
    "jar_repack_timestamp": 23,
    "clipboard_hack_evidence": 21,
    "minecraft_safe_mode": 20,
    "remote_access_active": 24,
    "rdp_session_active": 22,
    "temp_hack_binary": 26,
    "jar_self_deleted": 29,
    "recycle_hash_match": 18,
    "scheduled_task_suspicious": 23,
    "lolbins_extra_suspicious": 25,
    "deleted_mass_event": 21,
    "muicache_suspicious": 27,
    "run_mru_suspicious": 28,
    "typed_path_suspicious": 30,
    "recent_lnk_hack": 31,
    "windows_search_hack": 33,
    "amcache_hack_execution": 26,
    "userassist_suspicious": 27,
    "shimcache_suspicious": 26,
    "yara_java": 25,
    "ghost_client_config": 24,
    "ghost_client_registry": 24,
    "recycle_hack": 23,
    "hack_launcher_script": 22,
    "jump_list_suspicious": 21,
    "cloud_hash_match": 22,
    "injector_process": 29,
    "javaagent_injection": 28,
    "jdwp_debug_port": 28,
    "dns_cache_hack": 20,
    "hosts_minecraft_redirect": 27,
    "temp_jar_recent": 22,
    "litematica_printer": 23,
    "schematica_printer": 23,
}


def _conf01(issue: dict) -> float:
    try:
        c = float(issue.get("confidence") or 0)
    except (TypeError, ValueError):
        c = 0.0
    return c / 100.0 if c > 1.0 else max(0.0, min(1.0, c))


def rank_issues(issues: List[dict]) -> List[dict]:
    def key(i: dict):
        tipo = (i.get("tipo") or "").lower()
        alerta = (i.get("alerta") or "").upper()
        boost = _TYPE_BOOST.get(tipo, 0)
        if (i.get("categoria") or "").upper() == "INTEGRITY":
            boost = max(boost, 48)
        return (
            boost + _ALERT_SCORE.get(alerta, 0) * 10,
            _conf01(i),
            1 if (i.get("extra") or {}).get("related_count") else 0,
        )

    return sorted(issues or [], key=key, reverse=True)


def split_top_n(issues: List[dict], n: int = 5) -> Tuple[List[dict], List[dict]]:
    ranked = rank_issues(issues)
    # ss_verdict siempre primero si existe
    verdict = [i for i in ranked if (i.get("tipo") or "") == "ss_verdict"]
    rest = [i for i in ranked if (i.get("tipo") or "") != "ss_verdict"]
    top = verdict[:1] + rest[: max(0, n - len(verdict[:1]))]
    # evitar dupes en top
    top_ids = {id(x) for x in top}
    other = [i for i in ranked if id(i) not in top_ids]
    return top, other


def format_issue_line(issue: dict, idx: int) -> str:
    name = issue.get("nombre") or "N/A"
    tipo = issue.get("tipo") or "?"
    alerta = issue.get("alerta") or "?"
    ruta = issue.get("ruta") or issue.get("archivo") or ""
    ts = issue.get("timestamp") or issue.get("last_executed") or ""
    h = (issue.get("file_hash") or issue.get("sha256") or "")[:12]
    expl = (issue.get("explicacion") or "")[:160]
    rel = (issue.get("extra") or {}).get("related_count") or 0
    combo = issue.get("combination_penalty") or (issue.get("extra") or {}).get(
        "combination_penalty"
    )
    lines = [
        f"{idx}. [{alerta}] {name}",
        f"   tipo={tipo}",
    ]
    if ruta:
        lines.append(f"   ruta={ruta[:120]}")
    bits = []
    if ts:
        bits.append(f"t={ts[:19]}")
    if h:
        bits.append(f"hash={h}")
    if rel:
        bits.append(f"related={rel}")
    if combo:
        bits.append(f"combo={combo}")
    if bits:
        lines.append("   " + " · ".join(bits))
    if expl:
        lines.append(f"   por qué: {expl}")
    return "\n".join(lines) + "\n"


def render_results_text(widget, issues: List[dict], show_all: bool = False, top_n: int = 5) -> Dict[str, Any]:
    """Escribe en un ScrolledText Tk. Devuelve meta para botón expandir."""
    widget.delete("1.0", "end")
    total = len(issues or [])
    top, other = split_top_n(issues or [], n=top_n)
    verdict = next((i for i in (issues or []) if (i.get("tipo") or "") == "ss_verdict"), None)

    widget.insert("end", "ESCANEO COMPLETADO\n\n", "success")
    if verdict:
        vd = verdict.get("verdict_data") or {}
        widget.insert(
            "end",
            f"VEREDICTO: {vd.get('verdict') or verdict.get('nombre', '?')}  "
            f"risk={vd.get('risk_score', '?')}/100\n",
            "danger",
        )
        action = vd.get("staff_action") or ""
        if action:
            widget.insert("end", f"Acción staff: {action}\n", "warning")
        widget.insert("end", "\n", "info")

    tipos = {(i.get("tipo") or "") for i in (issues or [])}
    flags = []
    if tipos & {"remote_access_active", "rdp_session_active"}:
        flags.append("REMOTE")
    if "recycle_hash_match" in tipos:
        flags.append("HASH_PAPELERA")
    if any((i.get("combination_penalty") or (i.get("extra") or {}).get("combination_penalty"))
           for i in (issues or [])):
        flags.append("COMBO")
    if tipos & {"browser_hack_cookie", "wininet_hack_cookie"}:
        flags.append("COOKIE")
    if "prefetch_referenced_hack" in tipos:
        flags.append("PREF_REF")
    if "lnk_xaml_hijack" in tipos:
        flags.append("LNK_HIJACK")
    if flags:
        widget.insert("end", "Flags: " + " · ".join(flags) + "\n", "warning")

    widget.insert("end", f"Total hallazgos: {total}\n\n", "info")
    widget.insert("end", f"TOP {len(top)} (prioridad staff)\n", "warning")
    widget.insert("end", "-" * 40 + "\n", "info")
    for i, iss in enumerate(top, 1):
        tag = "danger" if (iss.get("alerta") or "").upper() == "CRITICAL" else "warning"
        widget.insert("end", format_issue_line(iss, i), tag)

    meta = {"other_count": len(other), "show_all": show_all, "top_n": top_n}
    if other and not show_all:
        widget.insert(
            "end",
            f"\n+{len(other)} hallazgos menores colapsados "
            f"(usá 'Mostrar todos' o revisá el panel).\n",
            "info",
        )
    elif other and show_all:
        widget.insert("end", f"\nRESTO ({len(other)})\n", "warning")
        widget.insert("end", "-" * 40 + "\n", "info")
        for i, iss in enumerate(other, len(top) + 1):
            tag = "danger" if (iss.get("alerta") or "").upper() == "CRITICAL" else "info"
            widget.insert("end", format_issue_line(iss, i), tag)
    elif not total:
        widget.insert("end", "No se encontraron elementos sospechosos.\n", "success")
    return meta
