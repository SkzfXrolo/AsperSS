# Read replica routing (Pack 48-H Round 6 · #154)

## Patrones

| Patrón | Descripción |
| --- | --- |
| Connection string dual | App detecta queries read-only y elige `DATABASE_REPLICA_URL` |
| Driver-level routing | SQLAlchemy session binds |
| Proxy (PgBouncer/PGCat) | routing por DB name o user |

## Reglas de routing Argus

- Reads tolerantes a lag → réplica:
  - Panel scans listados.
  - Reports históricos.
  - Stats dashboards.
- Reads críticos consistencia → primary:
  - Post-write read (read-your-writes).
  - Auth / billing actions.

## Fallback

Si réplica caída o lag > umbral → fallback automático a primary.

## Argus

Implementar como middleware app + flag por endpoint. Documentar lista en `docs/db/read-replicas-design.md` (Round 2).

## Referencias

- `docs/db/connection-pool.md`
