# Logical replication setup guide (Pack 48-H Round 5 · #134)

> **Sólo documentación.** No ejecutar en producción sin runbook y ventana aprobadas. PG ≥ 10.

## 1. Pre-requisitos en el publisher

```sql
SHOW wal_level;          -- debe ser 'logical'
SHOW max_replication_slots;
SHOW max_wal_senders;
SHOW max_logical_replication_workers;
```

Ajustes típicos (self-managed; Render puede no permitir todos):

```text
wal_level = logical
max_replication_slots = 10
max_wal_senders = 10
max_logical_replication_workers = 4
```

Reinicio requerido si se cambia `wal_level`.

## 2. Usuario de replicación

```sql
CREATE ROLE logical_rep WITH LOGIN REPLICATION PASSWORD '***';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO logical_rep;
-- o más restrictivo: sólo tablas publicadas
```

## 3. Crear publicación

```sql
CREATE PUBLICATION argus_core FOR TABLE scans, violations, ai_decisions_log
  WITH (publish = 'insert, update, delete');
```

Publicación de todo el schema (cuidado):

```sql
CREATE PUBLICATION argus_all FOR ALL TABLES;
```

Excluir tablas efímeras:

```sql
ALTER PUBLICATION argus_all DROP TABLE cache_sessions;
```

## 4. Preparar subscriber (schema compatible)

El subscriber debe tener **el mismo DDL** (columnas, tipos, defaults compatibles). Orden sugerido:

1. `pg_dump --schema-only` desde publisher → aplicar en subscriber.
2. Validar extensiones y search_path.
3. `REPLICA IDENTITY` en tablas sin PK antes de suscribir.

```sql
ALTER TABLE legacy_no_pk REPLICA IDENTITY FULL;  -- último recurso
```

## 5. Crear suscripción

```sql
CREATE SUBSCRIPTION argus_sub
CONNECTION 'host=publisher port=5432 dbname=argus user=logical_rep password=*** sslmode=require'
PUBLICATION argus_core
WITH (
  copy_data = true,
  create_slot = true,
  slot_name = 'argus_sub_slot'
);
```

`copy_data = true` hace snapshot inicial (puede ser pesado).

## 6. Verificación

Publisher:

```sql
SELECT * FROM pg_replication_slots;
SELECT * FROM pg_stat_replication;  -- física; lógica usa slots + workers
```

Subscriber:

```sql
SELECT * FROM pg_stat_subscription;
SELECT subname, received_lsn, latest_end_lsn FROM pg_stat_subscription_stats;
```

Lag aproximado:

```sql
SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) FROM pg_replication_slots WHERE slot_name = 'argus_sub_slot';
```

## 7. Operaciones comunes

Pausar aplicación de cambios (mantener slot):

```sql
ALTER SUBSCRIPTION argus_sub DISABLE;
```

Reanudar:

```sql
ALTER SUBSCRIPTION argus_sub ENABLE;
```

Eliminar suscripción y slot en publisher:

```sql
DROP SUBSCRIPTION argus_sub;
-- en publisher: DROP REPLICATION SLOT argus_sub_slot; si quedó huérfano
```

## 8. Añadir tabla a publicación existente

```sql
ALTER PUBLICATION argus_core ADD TABLE new_table;
```

En subscriber: crear tabla + `ALTER SUBSCRIPTION ... REFRESH PUBLICATION` (PG 15+ simplifica refresh).

## 9. Checklist Argus

- [ ] `wal_level=logical` confirmado.
- [ ] Slot monitoring (alerta si `lag_bytes` > umbral).
- [ ] DDL coordinado (Alembic en publisher primero, luego subscriber).
- [ ] No writes duplicados en tablas replicadas en subscriber (read-only role).
- [ ] SSL `require` o `verify-full` en connection string.

## Riesgos

- **Disk full** por slot sin consumo → monitorear `pg_replication_slots` + `pg_ls_waldir()`.
- **Schema drift** → aplicar migrations en orden en ambos nodos.
