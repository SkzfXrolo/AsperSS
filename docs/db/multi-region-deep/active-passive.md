# Active-passive across regions (Pack 48-H Round 5 · #139)

## Patrón

- **Primary** en región A (writes + reads críticos).
- **Standby async** en región B (read-only o frío).
- Failover manual/semi-auto promueve B si A cae.

## Ventajas Argus

- Simplicidad operativa vs active-active.
- Consistencia fuerte en primary único.
- Costo predecible (1 réplica).

## Desventajas

- Latencia escritura para usuarios lejos de A (mitigar con CDN/edge sólo para assets estáticos, no DB).
- RPO > 0 si async (lag réplica al fallo).

## Pasos de diseño

1. Elegir región primary cercana a mayoría de clientes pagadores.
2. Réplica en región distinta para **DR** (no sólo latency reads).
3. App routing: `DATABASE_PRIMARY_URL`, `DATABASE_REPLICA_URL` (reads eventualmente consistentes).

## Cutover DNS

TTL bajo antes de failover; usar proxy estable (PgBouncer DNS).

## Referencias

- `docs/db/multi-region.md` (Round 3)
- `docs/db/multi-region-deep/active-active.md`
