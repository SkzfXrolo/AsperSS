from __future__ import annotations

from scanners.startup_locations import scan_startup_locations
from scanners.services_anomalies import scan_services_anomalies


def scan_persistence_consolidated():
    startup = scan_startup_locations()
    services = scan_services_anomalies()
    suspicious_startup = [x for x in startup if x.get("score", 0) >= 2]
    return {
        "startup_total": len(startup),
        "startup_suspicious": suspicious_startup,
        "services_total": services.get("total_services", 0),
        "services_suspicious": services.get("suspicious", []),
    }

