# Alerting Runbook — Pack48-G

## Alertas críticas

1. **API down**
   - Trigger: healthcheck fail > 2 min
   - Acción: validar deploy, logs, DB, rollback si aplica

2. **Latency p99 alta**
   - Trigger: p99 > 500ms por 10 min
   - Acción: identificar endpoint caliente, habilitar mitigaciones (cache/rate-limit)

3. **Error rate alta**
   - Trigger: error_rate > 2% por 5 min
   - Acción: revisar release reciente, feature flags, rollback parcial

4. **DB saturation**
   - Trigger: conexiones > 85% por 10 min
   - Acción: revisar pooling, queries lentas, índices faltantes

## On-call

- Rotación semanal primaria/secundaria.
- Escalamiento a owner técnico si >30 min sin mitigación.

## Integraciones

- PagerDuty u Opsgenie para sev1/sev2.
- Slack/Discord para sev3 informativo.

## Postmortem mínimo

- timeline
- causa raíz
- impacto usuario
- acciones correctivas + due date
