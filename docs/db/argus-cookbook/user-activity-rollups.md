# User activity rollups (Pack 48-H Round 6 · #163)

## Métricas

- Logins/día.
- Acciones staff (audit).
- API calls por user.

## Tablas rollup

- `user_activity_daily(user_id, company_id, day, logins, actions)`.

## ETL

- Job nocturno consolida desde tablas raw.
- Reverso desde MV si datos sensibles.

## Argus

Útil para billing usage-based futuro y reportes engagement.

## Referencias

- `docs/db/reporting-layer.md`
