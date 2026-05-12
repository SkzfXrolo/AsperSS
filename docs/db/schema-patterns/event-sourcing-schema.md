# Event sourcing schema (Pack 48-H Round 6 · #162)

## Idea

Persistir **eventos** inmutables. El estado actual deriva replayando eventos.

```text
events(id, aggregate_id, aggregate_type, event_type, payload jsonb, created_at)
snapshots(aggregate_id, version, state jsonb, created_at)
```

## Pros

- Auditoría completa.
- Reconstrucción / time travel.
- CQRS natural.

## Cons

- Cambio mental.
- Queries actuales costosas sin proyecciones.
- Migraciones de schema de evento difíciles.

## Argus

No global. Adecuado para sub-dominios concretos (ban_history como event log).

## Referencias

- `docs/db/schema-patterns/cqrs-schema.md`
