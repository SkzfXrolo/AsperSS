"""
Puente entre el paquete scanners/ y el formato issues_found de ArgusApp.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List


def run_modular_scanners(timeout: int = 15, selected=None) -> Dict[str, Any]:
    try:
        from scanners._aggregator import run_scanners
        return run_scanners(selected=selected, timeout=timeout)
    except Exception as exc:
        return {"_error": {"ok": False, "error": str(exc)}}


def _issue(
    nombre: str,
    ruta: str,
    tipo: str,
    alerta: str = "SOSPECHOSO",
    confidence: float = 0.65,
    **extra,
) -> Dict[str, Any]:
    item = {
        "nombre": nombre,
        "ruta": ruta or "",
        "archivo": ruta or "",
        "tipo": tipo,
        "categoria": extra.pop("categoria", "SYSTEM"),
        "alerta": alerta,
        "confidence": confidence,
        "detected_patterns": extra.pop("detected_patterns", [tipo]),
        "explicacion": extra.pop("explicacion", nombre),
    }
    item.update(extra)
    return item


def results_to_issues(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convierte salida de run_scanners() a hallazgos del scanner principal."""
    issues: List[Dict[str, Any]] = []
    if not results:
        return issues

    err = results.get("_error")
    if err and not err.get("ok"):
        return issues

    for scanner_name, raw in results.items():
        if scanner_name.startswith("_") or not isinstance(raw, dict) or not raw.get("ok"):
            continue
        data = raw.get("result")
        if data is None:
            continue

        if scanner_name == "registry_anomalies" and isinstance(data, list):
            for row in data[:25]:
                key = row.get("key", "")
                name = row.get("name", "")
                value = str(row.get("value", ""))[:200]
                reason = row.get("reason", "suspicious_value")
                alerta = "CRITICAL" if reason == "hack_client_reference" else "SOSPECHOSO"
                conf = 0.88 if reason == "hack_client_reference" else 0.62
                issues.append(_issue(
                    nombre=f"Registro sospechoso: {name} → {value[:80]}",
                    ruta=key,
                    tipo="registry_anomaly_modular",
                    alerta=alerta,
                    confidence=conf,
                    categoria="REGISTRY",
                    detected_patterns=["registry_anomalies", row.get("reason", "suspicious_value")],
                    explicacion=f"Valor de inicio Run/IFEO sospechoso en {key}",
                ))

        elif scanner_name == "dns_artifacts" and isinstance(data, dict):
            for entry in data.get("hosts_entries", [])[:20]:
                low = entry.lower()
                if any(k in low for k in (
                    "minecraft", "mojang", "hypixel", "mineplex", "badlion",
                    "lunarclient", "feather", "aternos",
                )):
                    issues.append(_issue(
                        nombre=f"Hosts redirige dominio MC: {entry[:100]}",
                        ruta=r"C:\Windows\System32\drivers\etc\hosts",
                        tipo="hosts_minecraft_redirect",
                        alerta="CRITICAL",
                        confidence=0.88,
                        categoria="NETWORK",
                        detected_patterns=["dns_artifacts_hosts"],
                        explicacion="Entrada en hosts que puede redirigir tráfico de Minecraft.",
                    ))
            for anomaly in data.get("doh_dot_anomalies", [])[:10]:
                entry = anomaly.get("entry", "")
                issues.append(_issue(
                    nombre=f"DNS/hosts override: {entry[:80]}",
                    ruta=r"C:\Windows\System32\drivers\etc\hosts",
                    tipo="dns_override_modular",
                    alerta="POCO_SOSPECHOSO",
                    confidence=0.45,
                    categoria="NETWORK",
                ))

        elif scanner_name == "wmi_subscriptions" and isinstance(data, dict):
            filt = (data.get("filters") or "").strip()
            cons = (data.get("consumers") or "").strip()
            bind = (data.get("bindings") or "").strip()
            if filt or cons or bind:
                issues.append(_issue(
                    nombre="Suscripción WMI persistente detectada",
                    ruta="WMI:\\root\\subscription",
                    tipo="wmi_persistence_modular",
                    alerta="SOSPECHOSO",
                    confidence=0.72,
                    categoria="PERSISTENCE",
                    detected_patterns=["wmi_subscription"],
                    explicacion="EventFilter/Consumer WMI puede usarse para persistencia.",
                ))

        elif scanner_name == "scheduled_task_xml" and isinstance(data, list):
            for task in data[:15]:
                if not task.get("suspicious"):
                    continue
                task_path = task.get("task", "")
                cmd_parts = task.get("command") or []
                cmd = " ".join(str(c) for c in cmd_parts)[:200]
                issues.append(_issue(
                    nombre=f"Tarea programada sospechosa: {os.path.basename(task_path)}",
                    ruta=task_path or cmd,
                    tipo="scheduled_task_suspicious_modular",
                    alerta="SOSPECHOSO",
                    confidence=0.68,
                    categoria="PERSISTENCE",
                    detected_patterns=["scheduled_task_xml"],
                ))

        elif scanner_name == "credential_stores" and isinstance(data, list):
            vault_files = [x for x in data if x.get("type") == "vault_file"]
            if vault_files:
                issues.append(_issue(
                    nombre=f"Archivos Vault detectados: {len(vault_files)}",
                    ruta=vault_files[0].get("path", "Vault"),
                    tipo="credential_store_modular",
                    alerta="POCO_SOSPECHOSO",
                    confidence=0.42,
                    categoria="CREDENTIALS",
                ))

    return issues
