# Latency tradeoffs (Pack 48-H Round 5 · #139)

## RTT y diseño de queries

- Cada round-trip app↔DB suma RTT. **Chatty APIs** multiplican latencia.
- Mitigación: batch queries, GraphQL dataloader (`graphql-layer.md`), server-side joins.

## Ubicación de primary

| Primary en | Usuarios EU | Usuarios LATAM |
| --- | --- | --- |
| us-east | OK EU con fibra | +80–200ms típico |
| sa-east | penaliza EU | favorece LATAM |

## Sync replication cross-region

Ver `ha-patterns/synchronous-replication.md`: commit latency ≈ RTT.

## Réplicas de lectura

- Stale reads: documentar qué endpoints toleran lag (listados, analytics).
- No usar réplica para decisiones financieras inmediatas sin read-your-writes.

## Connection pooling

PgBouncer cerca de app en misma región que primary para reducir handshakes.

## Medición

- `pg_stat_activity` + APM traces correlacionados.
- Synthetic checks desde múltiples POP (Checkly).

## Referencias

- `docs/db/connection-lifecycle.md`
- `docs/db/read-replicas-design.md`
