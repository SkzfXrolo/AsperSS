# Foreign Data Wrappers (Pack 48-H Round 4 · #117)

## Qué es FDW

PG estándar para hacer **JOIN entre PG y otra fuente** (otra DB PG, Oracle, MongoDB, archivos CSV, Kafka, etc.) como si fueran tablas locales.

```
SELECT s.id, r.region_name
FROM scans s                    -- tabla local
JOIN region_dim r ON r.id = s.region_id   -- tabla via FDW (remote)
WHERE s.started_at > NOW() - INTERVAL '1 day';
```

## FDWs útiles para Argus

| FDW | Para qué | Disponibilidad |
| --- | --- | --- |
| `postgres_fdw` | otra PG (analytics replica, region B, partner DB) | built-in |
| `file_fdw` | CSV/TSV locales | built-in |
| `mongo_fdw` | MongoDB (futuro?) | third-party |
| `redis_fdw` | Redis (cache/sessions) | third-party |
| `kafka_fdw` | Kafka topics | third-party |
| `mysql_fdw` | MySQL legacy | third-party |
| `clickhousedb_fdw` | ClickHouse (OLAP) | third-party |

## Caso de uso #1 — Federar datos multi-region sin replication

Cliente EU corre en `PG-eu`; cliente US en `PG-us`. Para reportes ejecutivos cross-region:

```sql
-- en PG-us (origen del análisis)
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

CREATE SERVER pg_eu
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'eu-primary.internal', dbname 'argus_prod', port '5432');

CREATE USER MAPPING FOR app
    SERVER pg_eu
    OPTIONS (user 'reader_eu', password '${PASSWORD}');

IMPORT FOREIGN SCHEMA public
    LIMIT TO (scans, ai_decisions_log)
    FROM SERVER pg_eu INTO eu;

-- query cross-region
SELECT 'us' AS region, COUNT(*) FROM public.scans WHERE started_at::date = CURRENT_DATE
UNION ALL
SELECT 'eu', COUNT(*) FROM eu.scans WHERE started_at::date = CURRENT_DATE;
```

**Pro**: cero replication infra. **Con**: latencia WAN; pushdown limitado.

## Caso de uso #2 — Importar CSVs de partners

```sql
CREATE EXTENSION IF NOT EXISTS file_fdw;

CREATE SERVER csv_files FOREIGN DATA WRAPPER file_fdw;

CREATE FOREIGN TABLE partner_bans_csv (
    player_uuid UUID,
    ban_reason  TEXT,
    banned_at   TIMESTAMP
) SERVER csv_files
  OPTIONS (filename '/data/imports/partner-bans.csv', format 'csv', header 'true');

-- y luego
INSERT INTO ban_history (player_uuid, reason, source, created_at)
SELECT player_uuid, ban_reason, 'partner', banned_at
FROM partner_bans_csv
ON CONFLICT DO NOTHING;
```

## Caso de uso #3 — ClickHouse como capa OLAP

Para reportes pesados, exportamos al DW (ver `dw-export-design.md`); pero a veces se quiere queries ad-hoc desde PG hacia ClickHouse sin copiar.

```sql
CREATE EXTENSION IF NOT EXISTS clickhousedb_fdw;
CREATE SERVER ch FOREIGN DATA WRAPPER clickhousedb_fdw
    OPTIONS (host 'ch.internal', port '9000');
```

Pushdown: agregaciones se envían a ClickHouse, PG sólo recibe rows finales.

## Limitaciones de FDWs

| Tema | Impacto |
| --- | --- |
| Pushdown parcial | filtros sí, joins entre remotos a veces no |
| Estadísticas remotas | planner adivina cardinalidad → planes malos |
| Transacciones distribuidas | no garantiza atomicity cross-server |
| Tipos custom | requerir cast manual |
| Network latency | cada query atraviesa red |
| Auth | requiere user mapping; rotación manual de credenciales |

Mitigaciones:

- `ANALYZE foreign_table;` periódico (refresca estadísticas remotas).
- `fetch_size = 5000` (default 100) para batches mayores.
- `use_remote_estimate = true` (más lento de plan pero mejor).
- Usar **materialized views** locales con refresh para data que no cambia rápido.

## Cuándo NO usar FDW

- High-throughput inserts (cada INSERT atraviesa red).
- Joins muy complejos cross-server.
- Compliance: data nunca debe salir del region origen → FDW puede traerla.
- Cuando alcanza con `pg_dump` o ETL nocturno.

## Auditoría FDW

```sql
-- listar servers
SELECT * FROM pg_foreign_server;
-- listar foreign tables
SELECT * FROM information_schema.foreign_tables;
-- user mappings
SELECT srvname, usename FROM pg_foreign_server fs JOIN pg_user_mapping um ON fs.oid=um.umserver;
```

Backups: `pg_dump` NO incluye datos remotos (sólo el schema/foreign table definition). Es correcto.

## Recomendación Argus

| Use case | Recomendado? |
| --- | --- |
| Federar región US/EU para reportes ejecutivos | **sí**, postgres_fdw |
| Importar CSV partners (bans, blacklists) | **sí**, file_fdw |
| Reemplazar replication permanente | **no** |
| Sustituir DW analytics | **no**, usar ClickHouse vía FDW solo para queries ad-hoc |
| Reemplazar cache Redis | **no**, redis_fdw demasiado limitado |

## Roadmap

- Pack 50+: probar postgres_fdw entre staging y prod (para reproducir bugs con data real anonimizada).
- Pack 55+: si llega multi-region, postgres_fdw para reportes cross-region.
- Pack 60+: clickhouse_fdw si activamos DW analítico.

## Anti-patterns

1. ❌ Usar FDW para writes batch (cada INSERT cruza red).
2. ❌ Joins entre 3+ FDWs (planner enloquece).
3. ❌ Compartir credentials de admin en `CREATE USER MAPPING`.
4. ❌ Asumir transacciones atomic cross-server (no es 2PC por default).

## Referencias

- `multi-region.md` (#98)
- `dw-export-design.md` (Round 2)
- `multi-tenant-patterns.md` (#116)
