# PERFORMANCE NOTES

- `registry_anomalies`: ~80-300ms (depende de cantidad de keys).
- `dns_artifacts`: ~120-500ms (ipconfig/displaydns).
- `browser_history`: ~150-1200ms (copiado/lectura SQLite).
- `wmi_subscriptions`: ~400-2000ms (wmic overhead).
- `print_drivers`: ~300-1500ms (`pnputil /enum-drivers`).
- `firewall_rules`: ~300-2000ms (`netsh advfirewall`).

