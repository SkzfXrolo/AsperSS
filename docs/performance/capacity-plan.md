# Capacity Plan (Pack48-G)

## Supuestos de carga

- Usuarios activos actuales (estimado): 200–500/día.
- Growth mensual estimado: 10–20%.
- Picos: horario tarde/noche LATAM y eventos anticheat masivos.

## Modelo simple de capacidad

- Web API:
  - baseline 20–40 req/s
  - pico 80–120 req/s (polling + plugin traffic)
- DB:
  - lecturas dominantes (`/api/scans`, dashboard, AI queries)
  - escrituras por scans/violations/feedback

## Cuándo escalar

### Render

- Escalar plan cuando:
  - CPU > 70% sostenido 15 min,
  - p99 > 500ms sostenido,
  - error rate > 1% por saturación.

### DB

- Agregar read replicas cuando:
  - read-heavy queries saturan primario,
  - lag aceptable para vistas no críticas.

### CDN/Cloudflare

- Activar cache agresivo de estáticos y edge compresión.
- Proteger origen con rate-limit/WAF.

## Estimación de costos (orientativa)

- Tier actual: bajo costo, riesgo de saturación en picos.
- Tier medio: +50–150% costo, pero mejora fuerte en p95/p99.
- Tier alto: para crecimiento acelerado y multi-tenant más grande.

> Ajustar números finales con métricas reales de consumo de Render/DB del mes.
