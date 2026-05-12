# Datadog APM Setup — Pack48-G

## Backend Python

1. Instalar:
```bash
pip install ddtrace
```
2. Ejecutar app con tracer:
```bash
ddtrace-run gunicorn web_app.app:app
```
3. Variables recomendadas:
- `DD_ENV=prod`
- `DD_SERVICE=argus-web`
- `DD_VERSION=<git_sha>`

## Custom metrics sugeridas

- `argus.scans.created`
- `argus.oracle.evaluate.latency_ms`
- `argus.plugin.violations.ingest_rate`
- `argus.db.query.latency_ms` (tags: endpoint, table)

## Dashboards mínimos

- API p50/p95/p99 por endpoint.
- Error rate por endpoint.
- DB latency + pool saturation.
- Throughput scans/min y oracle eval/min.
