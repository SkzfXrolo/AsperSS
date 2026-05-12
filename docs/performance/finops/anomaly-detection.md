# Cost Anomaly Detection

Alertar cuando:
- gasto diario > +30% vs promedio 7d,
- costo por operación > +20% vs baseline.

Runbook:
1. identificar servicio/tenant causante,
2. verificar deploys recientes,
3. aplicar mitigación (rate limit, cache, rollback, right-size).
