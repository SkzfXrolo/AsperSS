from __future__ import annotations

from scanners._safe_runner import run_safe
from scanners import (
    registry_anomalies,
    dns_artifacts,
    credential_stores,
    wmi_subscriptions,
    com_objects,
    scheduled_task_xml,
    firewall_rules,
)


SCANNERS = {
    "registry_anomalies": registry_anomalies.scan_registry_anomalies,
    "dns_artifacts": dns_artifacts.scan_dns_artifacts,
    "credential_stores": credential_stores.scan_credential_stores,
    "wmi_subscriptions": wmi_subscriptions.scan_wmi_subscriptions,
    "com_objects": com_objects.scan_com_objects,
    "scheduled_task_xml": scheduled_task_xml.scan_scheduled_task_xml,
    "firewall_rules": firewall_rules.scan_firewall_rules,
}


def run_scanners(selected=None, timeout=20):
    names = selected or list(SCANNERS.keys())
    out = {}
    for n in names:
        fn = SCANNERS.get(n)
        if not fn:
            continue
        out[n] = run_safe(fn, timeout=timeout)
    return out

