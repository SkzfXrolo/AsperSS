# Log Format JSON Standard — Pack48-G

## Campos obligatorios

- `timestamp` (ISO8601 UTC)
- `level` (`DEBUG|INFO|WARN|ERROR`)
- `service` (`web|scanner|plugin`)
- `request_id`
- `trace_id`
- `user_id` (si aplica, ideal hash)
- `message`
- `latency_ms` (si aplica)

## Campos recomendados

- `endpoint`
- `method`
- `status_code`
- `error_code`
- `company_id`
- `scan_id`

## Ejemplo

```json
{
  "timestamp": "2026-05-12T08:10:11.123Z",
  "level": "INFO",
  "service": "web",
  "request_id": "req_4f9c",
  "trace_id": "tr_19ab",
  "user_id": "u_88d1",
  "endpoint": "/api/scans",
  "status_code": 200,
  "latency_ms": 84,
  "message": "list_scans served"
}
```
