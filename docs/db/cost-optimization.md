# Argus Projects — Cost optimization (DB) — Pack 48-H Round 2

## Tier actual (Render)

- Documentar en spreadsheet: **plan name**, **RAM**, **storage**, **precio/mes**, **conexiones max**.
- Re-evaluar cuando `pg_database_size` crece >50% del quota storage.

## Señales de upgrade prematuro

- CPU < 40% pero storage lleno → **archival** antes que tier más grande.
- Conexiones saturadas pero CPU baja → **PgBouncer** / pool en app.

## Growth rate proyectado

| Tabla | Driver | Proyección 12m |
| --- | --- | --- |
| `plugin_violations` | eventos anti-cheat | Lineal con MAU servidores |
| `ai_decisions_log` | cada eval Oracle | Lineal con violations |
| `scan_results` | hallazgos por scan | ~O(scans × avg_issues) |

**Fórmula rápida:** `violations_per_day = servers × avg_violations_per_server × 86400/avg_interval_sec` (orden de magnitud).

## Archival (cost-down)

- Mover blobs históricos (`screenshot` en `scans` si existe) a **S3 Glacier** con puntero `TEXT` URL.
- Particionar `scans` por `started_at` mensual → `DETACH PARTITION` + export a Parquet.

## Partitioning recomendado (antes de sharding)

```sql
-- Ejemplo conceptual PG10+ (no ejecutar sin ventana):
-- CREATE TABLE scans_2026_05 PARTITION OF scans FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

Beneficio: VACUUM y queries time-range más baratos.

## Índices no usados

- Revisar `monitoring-queries.sql` M2 mensualmente.
- `DROP INDEX CONCURRENTLY` sólo tras 14d con `idx_scan=0` **y** confirmación en staging.

## Read replica vs upsize

- Si p95 lectura > 100ms y writes <10% CPU → **réplica** más barato que duplicar RAM primario.

## Resumen presupuesto

| Prioridad | Acción | Ahorro estimado |
| --- | --- | --- |
| P0 | Cleanup `ai_decisions_log` / `discord_queue` | Storage ↓ |
| P1 | Archival screenshots | Storage ↓↓ |
| P2 | Partition + drop old partitions | IO ↓ |
| P3 | DW export + trim OLTP | OLTP size ↓ |
