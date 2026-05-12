# Major PG upgrade via logical replication (Pack 48-H Round 5 · #134)

Complementa `docs/db/zero-downtime-upgrade.md` (Round 3) con pasos orientados a **logical rep**.

## Objetivo

Migrar de **PG N** (publisher) a **PG N+1** (subscriber) con **mínimo downtime** (segundos a minutos de cutover).

## Fases

### Fase 0 · Preparación

- Dimensionar subscriber con **mismo o mayor** CPU/RAM/disk IOPS.
- Verificar extensiones disponibles en N+1.
- Baseline de performance (`pgbench`, queries críticas).

### Fase 1 · Subscriber vacío con schema

```bash
pg_dump --schema-only -h old -U owner -d argus | psql -h new -U owner -d argus
```

Aplicar migrations hasta mismo estado lógico que prod (Alembic revision idéntico).

### Fase 2 · Publicación y suscripción

En **old** (publisher N):

```sql
CREATE PUBLICATION upgrade_pub FOR ALL TABLES;
-- o lista acotada si hay tablas no necesarias
```

En **new** (subscriber N+1):

```sql
CREATE SUBSCRIPTION upgrade_sub CONNECTION '...old...' PUBLICATION upgrade_pub;
```

Monitorear catch-up hasta `lag ≈ 0`.

### Fase 3 · Validación continua

- Row counts muestra en tablas grandes (`COUNT(*)` en ventanas por `created_at` — evitar full count masivo en prod).
- Checks de integridad (`scripts/db/integrity-checks.sql`).
- App read-only contra **new** en staging con carga sintética.

### Fase 4 · Cutover

1. Poner app en **maintenance** breve (opcional si se usa proxy que drena conexiones).
2. `ALTER SUBSCRIPTION upgrade_sub DISABLE` (o dejar hasta último momento según estrategia).
3. Verificar LSN final y que no queden tx abiertas en old.
4. Actualizar `DATABASE_URL` a **new**.
5. Arrancar app en N+1.

### Fase 5 · Decomisión old

- Retener old read-only varios días como rollback.
- `DROP SUBSCRIPTION` en new cuando ya no se necesite slot en old.
- `DROP PUBLICATION` en old.

## DDL durante la migración

Congelar migrations destructivas durante catch-up. Cualquier DDL en old debe replicarse manualmente a new **antes** de que el evento genere divergencia en tablas no alineadas.

## Sequences post-cutover

En tablas con `SERIAL`/`IDENTITY` donde **new** recibió datos:

```sql
SELECT setval('scans_id_seq', (SELECT MAX(id) FROM scans));
```

## Render

Ver `render-limitations.md`: puede no ser posible sin instancia nueva + soporte. Plan B: dump/restore con ventana.

## Métricas de éxito

- RTO cutover < 15 min.
- RPO ≈ lag de replicación al momento del freeze (< 1 min típico bien dimensionado).
- Cero errores de aplicación post-switch en primeras 24h.
