# Sync vs async replication tradeoffs (Pack 48-H Round 6 · #154)

| Dimensión | Async | Sync |
| --- | --- | --- |
| RPO | > 0 (lag) | ≈ 0 (al menos en N standbys) |
| Throughput commit | alto | menor (RTT-bound) |
| Resiliencia red | tolera | sensible (puede degradar primary) |
| Operación | simple | requires quorum strategy |

## Hybrid

```text
synchronous_standby_names = 'FIRST 1 (rep_a, rep_b), rep_c, rep_d'
```

- 1 sync local (AZ misma región) + 2 async remoto.

## Argus

Pack 48-50: async (no aplica sync hasta self-host).

## Referencias

- `docs/db/ha-patterns/synchronous-replication.md`
