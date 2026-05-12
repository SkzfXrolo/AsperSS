# Anti-DDoS Strategy

## Layer 3/4

- CDN/WAF provider (Cloudflare) con mitigación volumétrica automática.
- upstream autoscaling y límites de conexión.

## Layer 7

- rate-limits por endpoint sensible,
- quotas por tenant/user/token,
- circuit-breaker en endpoints de costo alto (AI).

## Slowloris / HTTP flood

- timeouts cortos de headers/body en reverse proxy,
- límites de conexiones concurrentes por IP,
- `keepalive` y `client_body_timeout` ajustados.

## Operación

- playbook de escalamiento,
- dashboards p95/p99 + error rate + saturación,
- runbook de bloqueo temporal geográfico/ASN.
