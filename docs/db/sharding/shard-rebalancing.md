# Shard rebalancing (Pack 48-H Round 6 · #153)

## Cuándo

- Hot shard (tenant grande dispara CPU/IO).
- Nuevo nodo agregado.
- Tier upgrade asimétrico.

## Estrategias

| Estrategia | Descripción |
| --- | --- |
| Dual-write + backfill + cutover | seguro, complejo |
| `logical replication` por tabla | mover subset |
| `pg_dump`/`pg_restore` con ventana | simple, downtime |
| Citus `master_move_shard_placement` | si Citus |

## Pasos genéricos (zero-downtime)

1. Marcar shard origen "read-write + capture changes".
2. Snapshot inicial al destino.
3. Logical replication continua.
4. Validar lag ≈ 0 + checksums.
5. Cutover: switch routing.
6. Cleanup origen.

## Riesgos

- Inconsistencias durante cutover.
- Sequences (asignar rangos por shard).

## Argus

Documentación preventiva; no aplicable Pack 48-50 (no shards aún).

## Referencias

- `docs/db/sharding/horizontal-sharding.md`
- `docs/db/logical-replication/setup-guide.md`
