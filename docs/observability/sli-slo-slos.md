# SLI / SLO / Error Budget — Pack48-G

## SLIs propuestos

1. **Availability API**
   - `successful_requests / total_requests`
2. **Latency p99**
   - p99 de endpoints críticos (`/api/scans`, `/api/plugin/ai-evaluate`)
3. **Error rate**
   - `(5xx + timeout) / total`

## SLOs propuestos

- Uptime mensual: **99.5%**
- Latencia p99 API crítica: **< 500ms**
- Error rate global: **< 1%**

## Error budget

- Con 99.5% uptime: ~3h 39m de error mensual.
- Política:
  - si burn-rate alto: freeze de features no críticas,
  - priorizar fixes de confiabilidad/performance.
