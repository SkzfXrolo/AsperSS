# Argus Projects — Findings Pack 48 (audit DBA)

> Generado por subagente H del sprint Pack 48 al auditar el esquema completo. **NO se aplican patches** desde este worker — sólo documentación.
> Severidades: **HIGH** (riesgo de datos/seguridad / silent failure) · **MED** (deuda técnica con impacto operativo) · **LOW** (cosmético / convención).

---

## SEV-HIGH

### F-001 · `scans.company_id` se consulta pero **no existe**

**Localización:** `web_app/app.py:15733-15765` (función `_company_summary` y derivados).

**Descripción:** seis queries filtran por `scans.company_id`:

```py
cur.execute(f"SELECT COUNT(*) FROM scans WHERE company_id = {ph}", (cid,))
cur.execute("SELECT COUNT(*) FROM scans WHERE company_id = %s AND verdict = %s", ...)
# (...4 más...)
```

Pero **no hay** `CREATE TABLE scans (... company_id ...)` ni `ALTER TABLE scans ADD COLUMN company_id` en todo el repo. La columna nunca se creó.

**Comportamiento en PG:** la query lanza `psycopg2.errors.UndefinedColumn` y se captura por el try/except global, devolviendo `null` / `0`. El usuario ve la métrica como "0 scans" o "datos no disponibles" sin warning.

**Impacto:**
- Reportes per-empresa muestran 0 en panel SuperAdmin.
- Métricas de billing/quotas potencialmente vacías.
- Pack 42 estableció aislamiento por empresa pero esta tabla quedó fuera del scope.

**Solución sugerida (no aplicar desde H):**

1. Confirmar con owner si el aislamiento debe propagarse via `scans.company_id` directo o via `JOIN scan_tokens.created_by → users.company_id`.
2. Si direct: agregar `ALTER TABLE scans ADD COLUMN IF NOT EXISTS company_id INTEGER` + backfill desde `scan_tokens.created_by`. Crear índice `(company_id, started_at DESC)`.
3. Si via JOIN: cambiar las 6 queries para usar JOIN explícito. Más caro pero respeta single source of truth.

**Mi recomendación:** opción 1 (columna directa). El JOIN doble (scans → tokens → users) en cada lectura es costoso y `scans` es la tabla más leída del sistema.

---

### F-002 · `download_links.created_by` cambio de tipo en cada boot

**Localización:** `web_app/db_postgresql.py:468-477`.

```py
cursor.execute('''
    ALTER TABLE download_links
    DROP CONSTRAINT IF EXISTS download_links_created_by_fkey
''')
cursor.execute('''
    ALTER TABLE download_links
    ALTER COLUMN created_by TYPE VARCHAR(100) USING created_by::text
''')
```

**Descripción:** en cada boot se intenta dropear la FK y cambiar el tipo. Es no-op si ya está aplicado (porque ya es VARCHAR(100)), pero **el cast `USING created_by::text` re-escribe la columna entera incluso si ya es TEXT** — tabla bloqueada con `AccessExclusiveLock` durante todo el ALTER.

**Impacto:**
- Cold boot lento si la tabla tiene muchos rows.
- Lock causa deadlock con SELECTs concurrentes de descargas.
- El try/except global oculta el problema (silent fail).

**Solución sugerida:** mover a un script de migración one-shot (`scripts/db/migration-runbook.md`). En el código del init, sólo verificar `information_schema.columns` y skipear si ya es VARCHAR(100).

---

### F-003 · Cleanup automático cubre sólo 4 de ~15 tablas que crecen sin límite

**Localización:** `web_app/ai_maintenance.py:351 run_maintenance()`.

**Descripción:** el job de mantenimiento corre:
- `decay_learned_hack_patterns` → soft-disable, no DELETE.
- `deactivate_stale_legit_patterns` → soft-disable, no DELETE.
- `recompute_all_trust_scores` → UPDATE.
- `cleanup_company_cooldowns` → reset counters.

**No hace DELETE en ninguna tabla.** Las que crecen sin techo:

| tabla | crecimiento esperado | sin cleanup |
| --- | --- | --- |
| `ai_decisions_log` | append por cada violation procesada (~200/día/key) | ✗ |
| `plugin_violations` | append por cada check positivo (~varias k/día) | ✗ |
| `staff_audit_log` | append por cada acción staff | ✗ |
| `verdict_history` | append por cada cambio de verdict | ✗ |
| `evidence_fingerprints` | crece pero auto-dedup vía seen_count | parcial |
| `ai_feedback` | append append | ✗ |
| `ai_auto_labels` | append por cada ML run | ✗ |
| `discord_queue` | append + processed_at sólo se marca, no DELETE | ✗ |
| `ban_history` | append | ✗ (legal retention) |
| `scan_results` | append, cascade desde scans (pero scans no se borra) | ✗ |

Política recomendada en `scripts/db/cleanup-policy-pack48.sql`.

---

## SEV-MED

### F-010 · `staff_audit_log.timestamp` sugerencia rota en `ai_maintenance.suggest_db_indexes`

**Localización:** `web_app/ai_maintenance.py:281`.

```py
'sql_create': 'CREATE INDEX IF NOT EXISTS idx_audit_user_action ON staff_audit_log (user_id, action, timestamp DESC)',
```

El nombre real de la columna es **`created_at`**, no `timestamp` (ver `app.py:13226`). Si un admin copia/pega esta sugerencia desde el panel, PG lanza `UndefinedColumn`.

**Solución sugerida (no aplicar desde H):** corregir el snippet a `created_at DESC`.

---

### F-011 · `company_settings` DDL duplicado 3 veces en `app.py`

**Localización:** `app.py:6270`, `app.py:6361`, `app.py:13722`.

**Descripción:** la misma sentencia `CREATE TABLE IF NOT EXISTS company_settings (...)` se inlinea tres veces. Si alguien agrega una columna sólo en uno de los tres lugares, los otros dos quedarán out-of-sync hasta que tropiecen con el path. Como las tres son IF NOT EXISTS, la tabla ya existirá y los DDLs nuevos no se aplican (silent fail).

**Solución sugerida:** extraer a `_ensure_company_settings()` y llamar desde los tres callsites.

---

### F-012 · `auto_labels` vs `ai_auto_labels` — naming overlap

**Localización:** `ml_classifier.py:541` (creates `auto_labels`) y `app.py:2467` (creates `ai_auto_labels`).

**Descripción:** dos tablas distintas con propósito similar. `auto_labels` (Pack <40) etiqueta scans con `auto_verdict`. `ai_auto_labels` (Pack 45) etiqueta `decision_id` con `label REAL`. La diferencia funcional es clara pero el naming confunde a cualquier nuevo desarrollador.

**Solución sugerida:** renombrar `auto_labels` → `scan_auto_labels` (o consolidar si el flow ya no las usa). Requiere code grep antes de tocarlo.

---

### F-013 · `idx_*` con nombres colisionables en PG

**Localización:** `db_postgresql.py` líneas 114-551.

**Descripción:** PG comparte namespace de índices por schema (no por tabla). Hay 10+ índices con nombres como `idx_token`, `idx_active`, `idx_scan_id`, `idx_version`, `idx_username` creados sobre tablas distintas. Funciona porque cada uno cae en la primera tabla que ejecuta el CREATE, pero:

- `pg_stat_user_indexes` se vuelve ambiguo.
- Imposible saber a qué tabla pertenece un `idx_token` sin consultar `pg_indexes.tablename`.
- Si un futuro CREATE colisiona contra una tabla ya indexada, PG lanza error.

**Solución sugerida:** renombrar todos a `idx_<tabla>_<columna>`. Migration runbook lo cubre.

---

### F-014 · `idx_scans_started` y `idx_started_at` cubren la misma columna

**Localización:** `auth.py:448` y `db_postgresql.py:147`.

**Descripción:** `idx_started_at ON scans(started_at)` (asc) y `idx_scans_started ON scans(started_at DESC)` (sólo SQLite mirror). En SQLite ambos índices coexisten consumiendo doble el storage. En PG sólo se crea uno.

**Solución sugerida:** mantener uno solo, preferentemente DESC porque las queries de listado siempre son por scan más reciente.

---

### F-015 · `scan_tokens.token` y `scan_tokens.short_code` son ambos UNIQUE pero distintos

**Localización:** `db_postgresql.py:103`, `app.py:309`.

**Descripción:** `token VARCHAR(255) UNIQUE` (URL-safe largo) y `short_code VARCHAR(8) UNIQUE` (6 chars human-readable). Ambas UNIQUE constraints son OK, pero el código en `api_plugin_issue_token` no maneja la posible colisión de `short_code` (genera 20 intentos y desiste si no encuentra slot — `app.py:2252`).

**Comportamiento actual:** con ~30 chars y 6 posiciones, colisión a partir de ~24M tokens activos. Hoy ~irrelevante, pero a 100k tokens/día llegaríamos en <1 año.

**Solución sugerida:** ampliar `short_code` a 7-8 chars cuando el conteo activo supere 1M. Hoy: sólo monitorear.

---

### F-016 · `ban_history` no tiene `company_id` ni FK a `users`

**Localización:** `db_postgresql.py:163`.

**Descripción:** `ban_history` registra bans pero no propaga `company_id`. Cuando un staff ve "todos los bans históricos" no puede filtrarlo per-empresa sin JOIN a `scans.company_id` (que tampoco existe → ver F-001).

**Solución sugerida:** agregar `company_id INTEGER` + índice `(company_id, banned_at DESC)`. Es legal-required guardar bans incluso después de delete de empresa, así que **no** ON DELETE CASCADE.

---

### F-017 · `scan_results.feedback_status` sincronizado por backfill al boot

**Localización:** `db_postgresql.py:563-575`.

**Descripción:** en cada boot:

```sql
UPDATE scan_results sr
SET feedback_status = sf.staff_verification
FROM (SELECT DISTINCT ON (result_id) result_id, staff_verification
      FROM staff_feedback
      ORDER BY result_id, verified_at DESC) sf
WHERE sr.id = sf.result_id AND sr.feedback_status IS NULL
```

Esto se ejecuta en cada `init_postgresql_db()`. Si `scan_results` tiene 500k rows, este UPDATE recorre toda la tabla cada vez (porque el LEFT-style con NULL filter es OK pero el JOIN inner-style no usa índice óptimo).

**Solución sugerida:** mover a `scripts/db/cleanup-policy-pack48.sql` como migration one-shot. En `init_db_async` sólo actualizar rows nuevos (e.g. WHERE sr.created_at > NOW() - INTERVAL '1 day').

---

### F-018 · `discord_queue` sin DELETE — sólo soft-mark con `processed_at`

**Localización:** `db_postgresql.py:543`.

**Descripción:** las filas processed quedan para siempre. Si el worker procesa 100/min, en un año hay 50M+ rows con `processed_at NOT NULL` que sólo sirven para auditoría.

**Solución sugerida:** retention 14 días para procesados, indefinida para pendientes. Cubierto en `cleanup-policy-pack48.sql`.

---

## SEV-LOW

### F-020 · Naming inconsistente — singular vs plural

`statistics`, `staff_audit_log`, `staff_trust`, `app_meta`, `app_settings`,
`hack_blacklist`, `mod_whitelist`, `evidence_fingerprints` son singulares (o no
plurales obvios). El resto sigue plural. No es bug — sólo deuda cosmética.

### F-021 · `app_meta` + `app_settings` + `configurations` solapan

Tres tablas key-value:
- `app_meta` (`key VARCHAR(100) PK, value TEXT, updated_at`).
- `app_settings` (`key TEXT PK, value TEXT`).
- `configurations` (`id, key UNIQUE, value, description, updated_at`).

Cada una usada por código distinto. Solapamiento conceptual al 100%. Consolidar
a una sola tabla `app_kv (namespace, key, value, description, updated_at)` con
PK `(namespace, key)` sería más limpio.

### F-022 · `BOOLEAN DEFAULT 1` vs `BOOLEAN DEFAULT TRUE`

`auth.py` (SQLite) usa `DEFAULT 1` y `auth.py:166` mezcla `DEFAULT 1` con
`DEFAULT 0`. `db_postgresql.py` usa `DEFAULT TRUE/FALSE`. Compatible (drivers
normalizan) pero confuso al leer.

### F-023 · `DECIMAL(5, 2)` para `confidence` 0..1 desperdicia 3 dígitos

`scan_results.confidence`, `ai_analyses.confidence`, etc., son `DECIMAL(5,2)` →
permite valores hasta 999.99. Como sólo se usa 0..1 (con 2 decimales), `REAL` o
`NUMERIC(3,2)` sería más apropiado. Pre-existente, no urgente.

### F-024 · `ip_address` mixed VARCHAR(45) / TEXT

PG y SQLite usan `VARCHAR(45)` (cabe IPv6) pero `staff_audit_log.ip_address` es
también `VARCHAR(45)` — OK. Sin embargo, en `request.remote_addr` puede llegar
con `[::ffff:192.0.2.1]:54321` (con puerto) → necesita parsear antes de insertar
o ampliar a `VARCHAR(64)`.

### F-025 · Sin `created_at` en `scan_tokens` mirror SQLite

El CREATE TABLE en `auth.py:337` define `created_at` correctamente, pero el
mirror posterior en `db_postgresql.py:101` también. OK. (Comentario marcado
como verificado.)

---

## Findings adicionales (Rounds 4-6)

> Los IDs F-007 a F-019 fueron levantados en Rounds 2-6 dentro de los docs correspondientes; se consolidan aquí para trazabilidad única.

### F-007 · MED · Queries fantasma en `app.py` (~L810-828) — `fecha`/`scan_verdicts`/`empresas`

Subagente D coordina fix. Referencia: `docs/db/query-performance.md` (Round 2).

### F-008 · HIGH · Extensiones limitadas en Render (`pg_repack`, `pg_cron`, `pgaudit`, `pg_partman`)

Plan B documentado: cron externo + ventana para repack/cluster + log_statement como sustituto pgaudit. Ver `docs/db/render-runbook.md`, `docs/db/extensions-evaluation.md`.

### F-009 · HIGH · Backups Render dentro de Render (sin offsite)

Riesgo: dependencia total al proveedor. Acción: `backup-automation.sh` + S3 cross-region GPG (`backup-strategy.md`, `backup-advanced/cross-region-backup.md`).

### F-010 · MED · `idle_in_transaction_session_timeout` no configurado

Riesgo de locks por bugs app. Acción: setear `5min` (`statement-timeout.md`).

### F-011 · MED · Sin instrumentación regular de bloat

Autovacuum comportamiento desconocido. Acción: `scripts/db/bloat-check.sql` + `scripts/db/toolkits/pg_bloat_check.sql` en cron mensual.

### F-012 · MED · RLS no aplicado · aislamiento sólo por convención

Acción Pack 49: `pack49-migration-plan/rls-enablement.md` + `argus-scenarios/multi-tenant-rls.md`.

### F-013 · MED · Replicación lógica en Render requiere REVIEW

`wal_level=logical`, slots y networking dependen de tier. Ver `logical-replication/render-limitations.md`.

### F-014 · LOW · pgBackRest / Barman / `pg_basebackup` no aplican a managed Render

Sólo referencia para futuro self-host. `backup-advanced/*`.

### F-015 · MED · pgTAP y extensiones en CI deben validarse por tier

`testing/pgtap.md` SKIP gracefully cuando extensión ausente. Plan: imagen CI con pgTAP precargada.

### F-016 · MED · Falta default partition monitoring

Si se adopta partitioning, alertar si `*_default` recibe filas. Ver `partitioning-deep/partition-maintenance.md`.

### F-017 · MED · Stress / benchmark sin baseline persistido

Resultados de `scripts/db/bench/*` no comparados temporal. Acción: guardar resultados en repo infra y dashboards. Ver `data-observability.md`.

### F-018 · LOW · `polymorphic association` en `staff_audit_log` sin discriminator validado

Acción Pack 50+: agregar CHECK + tabla discriminator. `data-modeling/polymorphic-association.md`.

### F-019 · MED · Backfills sin tabla de tracking

No hay `backfill_runs` central. Acción: crear cuando se aborde F-001. `cookbook/data-backfills.md`.

---

## Anti-patterns generales identificados

1. **DDL embebido en código Python** — imposible auditar sin grep masivo, no
   funciona con herramientas SQL externas (DBeaver, Datagrip), no se versiona.
2. **`init_db_async` corre al boot** y ejecuta TODOS los ALTER y backfills cada
   vez. Cada deploy paga ese costo aunque la DB ya tenga schema final.
3. **Try/except global silencioso** — si el ALTER falla por lock_timeout, sólo
   se imprime un warning. No hay alerting. Schema queda inconsistente sin que
   nadie lo sepa.
4. **No hay versionado del schema** — no se sabe en qué Pack está la BD prod
   sin grep de columns.
5. **Sin tests del schema** — `tests/` (recién creado) no tiene ningún test que
   verifique invariantes. Las queries de `integrity-checks.sql` proveen una
   primera línea de defensa.
