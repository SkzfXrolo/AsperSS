# Argus Projects — Migration Runbook · Pack 48

> Guía operativa para aplicar los cambios sugeridos por el subagente H
> contra el cluster PostgreSQL de Render (producción).
> **No ejecutar nada de este runbook sin coordinación previa con el owner.**

Audiencia: DBA / SRE / owner del producto.
Entorno objetivo: PostgreSQL 14+ en Render (singleton DB managed).
Ventana recomendada: hora valle de tráfico (3–5 AM UTC). Tráfico actual no obliga downtime.

---

## Checklist previo (mandatorio)

- [ ] Anunciar mantenimiento al owner (Discord webhook `DISCORD_DEPLOY_WEBHOOK`).
- [ ] Confirmar que no hay deploy en curso (Render dashboard).
- [ ] Verificar que la última nightly de backup automático de Render está disponible (Render → Settings → Backups).
- [ ] Tener `psql` instalado localmente y la `DATABASE_URL` exportada.
- [ ] **Backup manual previo** (ver paso 1).
- [ ] Probar primero en un staging clone si existe (Render permite "Restore to new DB").

---

## Paso 1 · Backup completo previo

Aunque Render hace backups automáticos diarios, hacer uno manual ad-hoc antes de
cualquier migración. Lleva ~1-5 minutos según el tamaño.

```bash
# Desde una máquina con psql/pg_dump 14+:
export DATABASE_URL='postgresql://user:pass@host:5432/dbname'
mkdir -p backups/pack48
pg_dump --no-owner --no-acl --format=custom \
        --file=backups/pack48/argus-prepack48-$(date +%F-%H%M).dump \
        "$DATABASE_URL"
echo "Backup OK — $(ls -lah backups/pack48/ | tail -1)"
```

Restaurar (en caso de rollback):

```bash
pg_restore --clean --if-exists --no-owner --no-acl \
           --dbname="$DATABASE_URL" \
           backups/pack48/argus-prepack48-YYYY-MM-DD-HHMM.dump
```

**No hacer `pg_dump --format=plain`** — el formato `custom` permite restore parcial.

---

## Paso 2 · Verificar integridad previa

Antes de tocar el schema, correr el checklist de invariantes para tener un
baseline de "qué estaba roto antes" y poder distinguir nuevos problemas:

```bash
psql "$DATABASE_URL" -P pager=off -f scripts/db/integrity-checks.sql \
    > backups/pack48/integrity-pre-$(date +%F-%H%M).txt
```

Si alguna IC-** devuelve >0 rows, **investigar y arreglar manualmente antes**
de continuar (especialmente IC-05 a IC-13, que tocan FKs).

---

## Paso 3 · Aplicar índices recomendados (zero-downtime)

Los índices del `additional-indexes.sql` están escritos con `CREATE INDEX IF NOT
EXISTS` sin `CONCURRENTLY` para que el archivo sea idempotente y se pueda correr
entero en una transacción. **En producción** queremos `CONCURRENTLY` para no
bloquear las tablas grandes.

Procedimiento en PG14+ (zero-downtime, ~5–30 min total según tamaño):

```bash
# 1. Generar las versiones CONCURRENTLY (regex):
sed 's/CREATE INDEX IF NOT EXISTS/CREATE INDEX CONCURRENTLY IF NOT EXISTS/g' \
    scripts/db/additional-indexes.sql > /tmp/additional-indexes-concurrent.sql

# 2. CONCURRENTLY no puede ir dentro de DO $$ ni transacciones; verificar:
grep -n "BEGIN;\|COMMIT;\|DO \$\$" /tmp/additional-indexes-concurrent.sql

# 3. Ejecutar UNA SENTENCIA POR VEZ (psql -1 fallaría):
psql "$DATABASE_URL" -P pager=off -f /tmp/additional-indexes-concurrent.sql
```

**Si un `CREATE INDEX CONCURRENTLY` falla a mitad**, queda un índice "INVALID"
en `pg_indexes`. Detectarlo y dropearlo:

```sql
-- Detectar índices invalid:
SELECT indexrelname FROM pg_stat_user_indexes pgsi
JOIN pg_index pgi ON pgi.indexrelid = pgsi.indexrelid
WHERE NOT pgi.indisvalid;

-- Dropear el que aparezca:
DROP INDEX CONCURRENTLY IF EXISTS nombre_del_indice;

-- Reintentar el CREATE original.
```

Después de aplicar todos, refrescar stats:

```sql
ANALYZE VERBOSE;
```

---

## Paso 4 · Aplicar cleanup-policy (en batches, ventana valle)

`scripts/db/cleanup-policy-pack48.sql` ejecuta DELETE en bloques. Cada DO $$
bucle se sleepea 0.5–1s entre iteraciones para no saturar I/O.

**No correr el archivo entero de un golpe la primera vez.** Hacerlo bloque
por bloque, midiendo el efecto:

```bash
# Ejemplo: aplicar sólo BLOQUE 1 (ai_decisions_log 180d):
psql "$DATABASE_URL" -P pager=off <<'SQL'
DO $$
DECLARE deleted INT;
BEGIN
  LOOP
    DELETE FROM ai_decisions_log
    WHERE id IN (
      SELECT adl.id FROM ai_decisions_log adl
      LEFT JOIN ai_feedback af ON af.decision_id = adl.id
      WHERE adl.created_at < CURRENT_TIMESTAMP - INTERVAL '180 days'
        AND af.id IS NULL
      LIMIT 10000
    );
    GET DIAGNOSTICS deleted = ROW_COUNT;
    EXIT WHEN deleted = 0;
    RAISE NOTICE 'ai_decisions_log: deleted % rows', deleted;
    PERFORM pg_sleep(0.5);
  END LOOP;
END $$;
SQL
```

Después de cada bloque, correr `VACUUM ANALYZE <tabla>` para liberar el espacio
del MVCC. **NO usar `VACUUM FULL`** (toma `AccessExclusiveLock` y bloquea
TODA la tabla). Si después de varios meses la tabla quedó muy fragmentada,
considerar `pg_repack` (extensión separada).

**Métricas a monitorear durante el cleanup:**

- `pg_stat_activity`: queries bloqueadas (espera > 5s).
- Render dashboard CPU + Disk I/O.
- Logs de la app por errores tipo `canceling statement due to lock timeout`.

---

## Paso 5 · Verificar integridad posterior

```bash
psql "$DATABASE_URL" -P pager=off -f scripts/db/integrity-checks.sql \
    > backups/pack48/integrity-post-$(date +%F-%H%M).txt

diff backups/pack48/integrity-pre-*.txt backups/pack48/integrity-post-*.txt
```

Cualquier IC-** que aparezca con >0 rows en el post pero 0 en el pre es
una regresión del runbook — investigar antes de cerrar la ventana.

---

## Paso 6 · Tests funcionales

Sanity checks contra la app (no es exhaustivo, sólo smoke):

```bash
# 1. Login OK:
curl -s -o /dev/null -w "%{http_code}" https://<render-app>.onrender.com/login
#    Esperar 200

# 2. Endpoint de scans:
curl -s -H "Cookie: ..." https://<render-app>.onrender.com/api/scans?limit=5 | jq '.success'
#    Esperar true

# 3. AI Health:
curl -s -H "Cookie: ..." https://<render-app>.onrender.com/api/admin/ai-health | jq '.metrics'

# 4. Plugin issue token:
curl -s -X POST -H "X-Argus-Plugin-Key: <key>" \
     -d '{"staff":"test","target":"test","reason":"runbook"}' \
     https://<render-app>.onrender.com/api/plugin/issue-token
```

---

## Plan de rollback

Cada paso es reversible si se ejecuta correctamente, **excepto los DELETE de
cleanup** (los datos sí o sí se pierden — por eso el backup).

### Rollback de índices (paso 3)

```sql
-- Eliminar todos los índices Pack 48-H:
DO $$
DECLARE rec RECORD;
BEGIN
  FOR rec IN
    SELECT indexrelname FROM pg_stat_user_indexes
    WHERE indexrelname LIKE 'idx_p48h_%'
  LOOP
    EXECUTE 'DROP INDEX CONCURRENTLY IF EXISTS ' || quote_ident(rec.indexrelname);
  END LOOP;
END $$;
```

### Rollback de cleanup (paso 4)

NO existe rollback parcial — los rows están borrados. Las opciones son:

1. **Restore completo** desde `backups/pack48/argus-prepack48-...dump`.
2. **Restore parcial** a una DB temporal y reinsertar sólo las tablas afectadas:
   ```bash
   # Crear DB scratch
   createdb argus_restore_temp
   pg_restore --no-owner --dbname=argus_restore_temp backups/pack48/argus-prepack48-*.dump
   # Volcar la tabla afectada y reinsertar:
   pg_dump --table=ai_decisions_log --data-only --dbname=argus_restore_temp \
           | psql "$DATABASE_URL"
   ```

---

## Cambios de schema NO automatizados (revisar caso por caso)

Estos cambios requieren más planificación porque afectan al código de la app y
no pueden aplicarse sin coordinación dev+ops:

### A) `scans.company_id` — F-001 (SEV-HIGH)

**Cambio requerido:**

```sql
ALTER TABLE scans ADD COLUMN company_id INTEGER;
-- Backfill desde scan_tokens (created_by → users.username → users.company_id):
UPDATE scans s
SET    company_id = u.company_id
FROM   scan_tokens st
JOIN   users u ON u.username = st.created_by
WHERE  s.token_id = st.id
  AND  s.company_id IS NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_p48h_scans_company_started
    ON scans (company_id, started_at DESC);
```

**Pre-deploy:** confirmar con el owner que ningún staff hace inserts manuales
con `created_by` que no sea username válido.
**Post-deploy:** validar que el codepath en `app.py:15733-15765` ya tiene
contraparte real. Las queries silently-failing pasarán a devolver resultados.
**Riesgo:** cambia el comportamiento observable en panel SuperAdmin.

### B) `staff_audit_log.timestamp` → `created_at` en `ai_maintenance` — F-010

**Cambio requerido:** PR sobre `web_app/ai_maintenance.py` línea 281 (single
character fix). NO requiere migración DB.

### C) Consolidación `app_meta` / `app_settings` / `configurations` — F-021

Trabajo de varias horas. Mejor diferir a Pack 49.

### D) Renombrar índices duplicados — F-013

Trabajo de varias horas. Puede hacerse en paralelo con el roll-out gradual.
Procedimiento:

```sql
-- Por cada índice colisionable:
ALTER INDEX idx_token RENAME TO idx_scan_tokens_token;
-- ...
```

Es transaccional y rápido. Pero requiere actualizar `db_postgresql.py` para que
el próximo CREATE IF NOT EXISTS no recree el viejo nombre.

---

## Calendar sugerido

| Día | Actividad | Riesgo | Reversible |
| --- | --- | --- | --- |
| D-7 | Compartir runbook con owner, review | bajo | sí |
| D-3 | Aplicar a staging (clone DB) | bajo | sí |
| D-1 | Anunciar ventana en Discord | bajo | sí |
| D   | Backup → integridad pre → índices → integridad post → smoke tests | medio | parcial (índices sí, cleanup no) |
| D+1 | Cleanup BLOQUE 1 (ai_decisions_log) | medio | **no** sin restore |
| D+2 | Cleanup BLOQUES 2-8 | medio | **no** sin restore |
| D+3 | Cleanup BLOQUES 9-12 | medio | **no** sin restore |
| D+7 | Revisar `pg_stat_user_indexes` y dropear unused | bajo | sí |
| D+14 | Aplicar F-001 (scans.company_id) si owner aprueba | alto | sí (con backup) |

---

## Snippets útiles

### Tamaño actual por tabla (top 20)

```sql
SELECT relname AS table_name,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
       pg_size_pretty(pg_relation_size(relid))       AS table_size,
       pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid)) AS index_size,
       n_live_tup AS row_estimate
FROM   pg_stat_user_tables
ORDER  BY pg_total_relation_size(relid) DESC
LIMIT  20;
```

### Bloqueos en vivo

```sql
SELECT pid, usename, pg_blocking_pids(pid) AS blocked_by, query
FROM   pg_stat_activity
WHERE  state <> 'idle'
  AND  pg_blocking_pids(pid)::TEXT <> '{}';
```

### Cancelar una query bloqueada

```sql
SELECT pg_cancel_backend(<pid>);
-- Si no responde:
SELECT pg_terminate_backend(<pid>);
```

### Verificar índice nuevo en uso

```sql
SELECT relname, indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
FROM   pg_stat_user_indexes
WHERE  indexrelname LIKE 'idx_p48h_%'
ORDER  BY idx_scan DESC;
```

---

## Contacto

Issues, dudas, post-mortem: bandeja del owner del proyecto. Tag `pack48-H-runbook`
en el commit/PR/issue para enlazar de vuelta a esta documentación.
