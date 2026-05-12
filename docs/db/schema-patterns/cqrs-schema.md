# CQRS schema (Pack 48-H Round 6 · #162)

## Idea

Separar **modelo de escritura** del **modelo de lectura**:

- Writes a tablas normalizadas.
- Reads desde MV o tablas optimizadas.

## Argus pragmático

- Writes: `scans`, `violations` (normalizado).
- Reads panel: `mv_daily_scan_stats`, `mv_player_profiles_summary`.

## Coordinación

- MV refresh CONCURRENTLY.
- CDC para read-store externo si crece (futuro).

## Referencias

- `docs/db/materialized-views.md`
- `docs/db/cdc-design.md`
