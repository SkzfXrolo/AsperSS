# Synchronous replication (Pack 48-H Round 5 · #136)

## Objetivo

Reducir **RPO** a ~0 en pérdida del primario: el commit no se confirma al cliente hasta que el WAL está **durably** en al menos N standbys.

## Parámetros clave

```text
synchronous_commit = on | remote_apply | remote_write | local
synchronous_standby_names = 'FIRST 1 (rep_a,rep_b)'
```

| Valor | Tradeoff |
| --- | --- |
| `remote_write` | standby recibió WAL en OS cache; más rápido, menos fuerte |
| `on` (default remote flush) | standby flush a disk |
| `remote_apply` | standby aplicó cambios visibles; más lento, más fuerte |

## Tradeoffs

| Pro | Contra |
| --- | --- |
| RPO casi cero | Latencia de commit ↑ (especialmente WAN) |
| Menor riesgo split-brain si operado bien | Throughput TPS ↓ |
| Mejor historia para compliance | Complejidad de quorum |

## Latencia multi-región

Sync cross-region típicamente **mata** TPS: commits esperan RTT ida-vuelta.

**Recomendación Argus**: sync **intra-región** (AZ local); async a región DR.

## Witness

Combinar con **witness** (ver `witness-server.md`) para evitar split-brain en quorums automáticos.

## Referencias

- PostgreSQL docs: Synchronous Replication
- `docs/db/multi-region-deep/latency-tradeoffs.md`
