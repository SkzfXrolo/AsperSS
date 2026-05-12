# Prometheus + Grafana (self-hosted) — Pack48-G

## Arquitectura mínima

- Prometheus scrapea:
  - Flask metrics endpoint (`/metrics`)
  - node exporter
  - postgres exporter
- Grafana consulta Prometheus y define alertas.

## Exporters recomendados

- `prometheus_flask_exporter` (HTTP metrics)
- `node_exporter` (host metrics)
- `postgres_exporter` (DB)

## Dashboards clave

1. API Latency (p50/p95/p99)
2. API Error Rate (4xx/5xx)
3. DB health (connections, slow queries)
4. Infra (CPU, RAM, disk I/O)
5. Negocio (scans/min, oracle eval/min)

## Alertas mínimas

- p99 > 500ms por 10 min
- error_rate > 2% por 5 min
- uptime probe fail > 2 min
