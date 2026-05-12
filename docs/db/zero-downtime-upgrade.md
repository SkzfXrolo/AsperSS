# Zero-downtime PG major upgrade (Pack 48-H Round 3 · #97)

## Por qué no usar `pg_upgrade` directo

`pg_upgrade` requiere **parar** el primario durante el binary swap (~30s a varios minutos, según extensions y stats). En Argus eso significa que el plugin MC pierde latidos y el panel devuelve 5xx. Inaceptable para SLA del Pack 48+.

**Solución: logical replication**. Levantamos una réplica corriendo la versión nueva, sincronizamos por replication slot lógica, y cortamos tráfico con un cutover de **<5s**.

## Flow general (PG15 → PG16, ejemplo)

```
PG15 (primario actual)  ─── logical replication slot ───►  PG16 (nuevo, vacío)
        │                                                       │
        └── app via PgBouncer/DNS                                │
                                                  cutover: DNS/port swap
                                                                 ▼
                                                       PG16 toma writes
```

## Requisitos previos

| Item | Validar |
| --- | --- |
| `wal_level = logical` | sí (Render ofrece esto en tiers Pro+) |
| Todas las tablas con `REPLICA IDENTITY FULL` o PK | check `\d+ table` |
| No DDL durante replicación | freeze de migrations |
| Tier nuevo disponible (PG16) | revisar Render console |
| `pg_dump` schema testeable | sí |
| Backups previos | `pg_dump --format=custom` + S3 |

## Pasos detallados

### 0. Pre-flight (D-7)

1. Listar **extensiones** actuales:
   ```sql
   SELECT extname, extversion FROM pg_extension;
   ```
   Verificar que cada una tiene paquete para la nueva major version.
2. Auditar **funciones** y **operadores** removidos/cambiados entre versiones (release notes oficiales).
3. Lanzar el upgrade en staging primero (clone de prod).

### 1. Provisionar instancia destino (D-3)

- Render: crear nuevo PG service en mismo region y red interna, versión 16.x.
- Variable `DATABASE_URL_NEXT` apunta al nuevo.

### 2. Volcar schema (D-1)

```bash
pg_dump --schema-only --no-owner --no-acl \
        --dbname=$DATABASE_URL > schema_pg15.sql

# Importar al destino
psql --dbname=$DATABASE_URL_NEXT < schema_pg15.sql
```

> Si hay **extensions** custom: pre-instalarlas en destino antes del `psql < schema_pg15.sql`.

### 3. Crear publication en origen

```sql
-- en PG15 (primario actual)
CREATE PUBLICATION argus_pub FOR ALL TABLES;
```

### 4. Crear subscription en destino

```sql
-- en PG16 (nuevo)
CREATE SUBSCRIPTION argus_sub
  CONNECTION 'host=PG15_HOST port=5432 dbname=argus_prod user=replicator password=...'
  PUBLICATION argus_pub
  WITH (copy_data = true, create_slot = true, slot_name = 'argus_upg_slot');
```

PG16 ahora hace COPY inicial + lee WAL desde el slot.

### 5. Monitorear lag (D, durante ventana)

```sql
-- en PG16
SELECT subname, latest_end_time, NOW() - latest_end_time AS lag
FROM pg_stat_subscription;

-- en PG15
SELECT slot_name, active, restart_lsn,
       pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS bytes_behind
FROM pg_replication_slots;
```

**Gate**: lag < 1s sostenido durante ≥10 min.

### 6. Backfill de secuencias

Logical replication **no** sincroniza secuencias. Hay que copiarlas explícitamente:

```sql
-- en PG15
SELECT 'SELECT setval(' || quote_literal(sequencename) || ',' ||
       last_value || ');' FROM pg_sequences;
-- Aplicar el resultado en PG16.
```

### 7. Cutover (ventana <5s)

1. En PG15: `ALTER SYSTEM SET default_transaction_read_only = on;` + `pg_reload_conf()`.
   - Las apps ahora reciben error en writes pero sirven reads.
2. Esperar a que `pg_stat_subscription.latest_end_lsn` en PG16 alcance `pg_current_wal_lsn()` de PG15.
3. Re-ejecutar setval de secuencias.
4. Cambiar variable de entorno / DNS / PgBouncer config: app → PG16.
5. Confirmar primer insert exitoso en PG16.
6. Quitar read-only de PG15 (por si rollback) — sigue corriendo en sombra ~24h.

### 8. Post-cutover

- 24h: PG15 sigue activo como fallback.
- Monitorear errores y métricas (cache hit, latency).
- Si todo OK: `DROP SUBSCRIPTION argus_sub` (en PG16) y `DROP PUBLICATION argus_pub` (en PG15), luego decommissionar PG15.

## Rollback plan

Si en post-cutover detectamos regression crítica:
1. Cambiar DNS/env back a PG15.
2. Logical replication en **dirección inversa** (PG16 → PG15) durante el período en que PG16 estuvo writeable.
3. Sólo viable si PG15 sigue arriba (≤24h).

## Render specifics

| Tema | Acción |
| --- | --- |
| Network: PG16 debe ser accesible desde PG15 (private network) | Verificar Render egress/ingress |
| Credenciales replicator | crear rol en PG15 con `REPLICATION` |
| `wal_keep_size` | aumentar a 5GB durante upgrade |
| DNS swap | Render hostnames son fijos; usar variable `DATABASE_URL` y rolling deploy de la app |
| Extensions Render | si Render no las tiene en versión 16, postergar |

## Riesgos

| Riesgo | Mitigación |
| --- | --- |
| DDL en ventana → ruptura de replicación | Freeze (banner en CI/CD) |
| Secuencias atrás (id collisions) | Step 6, doble-check |
| Slot inactivo → disk full | Monitor + auto-drop si llevamos >30min sin avanzar |
| Tipo de dato cambió entre versiones | Validar con `\d+` antes |
| `pg_repack`/`pg_partman` incompatibles | Pre-validar versions |

## Frecuencia

- PG saca major cada 12 meses.
- Soporte upstream: 5 años por major.
- Recomendado: upgradar **una versión** atrás de la última (Argus en PG15 cuando 16 está estable, PG16 cuando 17 está estable).

## Validación post-upgrade (smoke)

```sql
-- counts
SELECT 'scans'         AS t, COUNT(*) FROM scans
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'companies', COUNT(*) FROM companies;

-- random row check
SELECT id, started_at FROM scans ORDER BY random() LIMIT 5;

-- index usage
SELECT relname, idx_scan FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND schemaname='public';
```

App-level: ver `dr-drill-plan.md` smoke checklist.
