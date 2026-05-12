# DB anti-patterns (Pack 48-H Round 4 · #132)

Catálogo de prácticas a **evitar** en Argus. Cada item: descripción, consecuencia, fix.

## Schema design

### 1. Polymorphic FKs sin discriminator real

❌ `target_id BIGINT, target_type TEXT` sin FK ni check de coherencia.
**Consecuencia**: leaks, orphans, queries inseguras.
✅ Tabla por tipo o supertype + subtype con FK explícitas.

### 2. Stringly-typed enum

❌ `status VARCHAR(50)` con valores `'pending', 'paid', 'PAID', 'Paid', 'ok'` sin CHECK.
**Consecuencia**: variantes con typos, lógica rota.
✅ `status TEXT CHECK (status IN (...))` o ENUM type.

### 3. JSON blobs como excusa para no diseñar

❌ Todo en `data JSONB` sin schema.
**Consecuencia**: imposible indexar, queries slow, validación cero.
✅ JSONB para extensiones legítimas; columnas tipadas para fields conocidos.

### 4. UUID v4 como PK con secuencial implícito

❌ `id BIGSERIAL` + `external_uuid UUID` ambos con índice + se usa el UUID en queries.
**Consecuencia**: índice doble; UUID v4 random fragmenta btree.
✅ Decidir: PK UUID v7/v6 (orden temporal) **o** BIGSERIAL como PK con uuid sólo external.

### 5. No PK / no created_at

❌ Tabla sin PK ni timestamp.
**Consecuencia**: imposible deduplicar, retention, replicación.
✅ Siempre PK + `created_at TIMESTAMPTZ DEFAULT NOW()`.

### 6. Multi-tenant sin `company_id` (F-001 redux)

❌ Tabla con datos cross-tenant sin `company_id`.
**Consecuencia**: leak entre tenants, imposible RLS.
✅ `company_id INT NOT NULL REFERENCES companies(id)` + índice + RLS.

### 7. Booleano "deleted_at" sin filtro consistente

❌ `deleted_at TIMESTAMPTZ` y olvidan `WHERE deleted_at IS NULL` en queries.
**Consecuencia**: rows soft-deleted leakeados.
✅ View `active_<table>` con filtro built-in, o RLS.

### 8. Naming inconsistente

❌ `created_at`, `createdAt`, `creation_date`, `fecha_creacion` mezclados.
**Consecuencia**: confusión, queries rotas.
✅ snake_case, `created_at`/`updated_at` siempre.

### 9. Singular vs plural tablas

❌ `user` (singular reserved-word) y `scans` (plural).
**Consecuencia**: quoting needed, sorpresa.
✅ Plural siempre.

### 10. Wide tables (>50 cols)

❌ Tabla con 80 columnas, mitad NULL.
**Consecuencia**: row width grande, fetches lentos, TOAST.
✅ Normalizar a sub-tablas o JSONB para sparse.

## Indexing

### 11. Index todo

❌ Crear índice por cada WHERE imaginable.
**Consecuencia**: writes lentos, espacio desperdiciado.
✅ Index lo que duele en producción (mide con `pg_stat_user_indexes`).

### 12. Index redundante

❌ `idx_a(col1)` + `idx_b(col1, col2)`. El primero es prefix del segundo.
**Consecuencia**: write penalty doble.
✅ Drop `idx_a` (a menos que sea unique).

### 13. CREATE INDEX en horario pico (no CONCURRENTLY)

❌ `CREATE INDEX idx ON big_table(...);` durante prod.
**Consecuencia**: lock writes durante minutos.
✅ `CREATE INDEX CONCURRENTLY ...`.

### 14. Index sobre boolean baja selectividad

❌ `CREATE INDEX ON users(is_active)` donde 99% son `true`.
**Consecuencia**: index inútil, never used.
✅ Partial index: `WHERE is_active = false`.

### 15. Functional index pero query no usa la función

❌ `CREATE INDEX ON users(lower(email))` y query `WHERE email = '...'`.
**Consecuencia**: index no se aplica.
✅ Match: `WHERE lower(email) = lower(...)`.

## Querying

### 16. SELECT *

❌ `SELECT * FROM big_table` y app sólo usa 2 cols.
**Consecuencia**: I/O desperdiciado, TOAST hit.
✅ Pedir columnas explícitas.

### 17. N+1

❌ Loop en app: `for x in xs: db.query("SELECT * FROM y WHERE id=?", x.y_id)`.
**Consecuencia**: 1000 queries vs 1.
✅ JOIN o `WHERE id IN (...)` o ORM dataloader.

### 18. OR mata el plan

❌ `WHERE a=1 OR b=2` sin índice covering.
**Consecuencia**: Seq Scan.
✅ `UNION ALL` o re-modelar.

### 19. Casteo bloquea index

❌ `WHERE id::text = '42'` sobre `id INT`.
**Consecuencia**: no usa index, full scan.
✅ Comparar con tipo nativo.

### 20. Funciones en columna izquierda

❌ `WHERE date_trunc('day', created_at) = current_date`.
**Consecuencia**: no usa index sobre `created_at`.
✅ `WHERE created_at >= current_date AND created_at < current_date + 1`.

### 21. LIKE '%foo%' en tabla grande sin trigram

❌ `WHERE name LIKE '%bar%'`.
**Consecuencia**: full scan.
✅ `pg_trgm` GIN index, o full-text search.

### 22. `LIMIT N` sin `ORDER BY`

❌ `SELECT ... LIMIT 10` sin ORDER.
**Consecuencia**: resultados no deterministic.
✅ Siempre ORDER BY estable (e.g. PK).

### 23. `count(*)` sobre tabla grande "para mostrar paginación"

❌ `SELECT count(*) FROM scans` para footer del UI.
**Consecuencia**: seq scan caro.
✅ Estimate vía `pg_stat_user_tables.n_live_tup` o `reltuples`. Si se necesita exact, cachear.

### 24. `ORDER BY random()`

❌ "Dame 10 aleatorios": `ORDER BY random() LIMIT 10`.
**Consecuencia**: full scan + sort.
✅ Reservoir sampling, `TABLESAMPLE`, o sorted aproximaciones.

### 25. `IN (...)` con miles de elementos

❌ `WHERE id IN (id1, id2, ..., id5000)`.
**Consecuencia**: query plan blow-up.
✅ `JOIN unnest(array[...])` o tabla temp.

## Transactions

### 26. Long-running transactions abiertas

❌ App abre tx, hace HTTP call de 30s sin commit/rollback.
**Consecuencia**: locks, autovacuum starvation.
✅ Tx cortas; HTTP fuera de tx.

### 27. SELECT FOR UPDATE sin LIMIT/WHERE

❌ `SELECT * FROM queue FOR UPDATE`.
**Consecuencia**: lock toda la tabla.
✅ `FOR UPDATE SKIP LOCKED LIMIT N` (queue pattern).

### 28. Idle in transaction olvidados

❌ Conexión `idle in transaction` por horas.
**Consecuencia**: bloated, locks.
✅ `idle_in_transaction_session_timeout = '5min'`.

### 29. SAVEPOINT abuso

❌ Cada query en su SAVEPOINT (algunos ORMs por default).
**Consecuencia**: overhead.
✅ Sólo donde necesitás partial rollback.

## Migrations

### 30. ALTER COLUMN TYPE en tabla grande durante prod

❌ `ALTER TABLE big ALTER COLUMN x TYPE bigint;` en horario pico.
**Consecuencia**: full rewrite + lock minutos/horas.
✅ Dual-column dual-write (ver `migration-tooling-deep.md`).

### 31. Drop column inmediato

❌ Drop una col en la misma release que app deja de usarla.
**Consecuencia**: si rollback necesario, app vieja explota.
✅ 2 releases: stop using → drop.

### 32. Backfill UPDATE 10M rows en un statement

❌ `UPDATE big SET new_col = old_col;`.
**Consecuencia**: lock, WAL bomb, replicación lag.
✅ Batches `UPDATE ... WHERE id BETWEEN x AND y LIMIT 10k`.

### 33. ADD CONSTRAINT NOT NULL sin paso intermedio

❌ Add NOT NULL directo sobre col existente con datos.
**Consecuencia**: scan + lock SHARE.
✅ CHECK NOT VALID + VALIDATE + SET NOT NULL.

### 34. Auto-generated migration sin review

❌ `alembic --autogenerate` + commit sin leer.
**Consecuencia**: drop unintended, rename misdetected.
✅ Review humano.

## Operations

### 35. VACUUM FULL en producción

❌ Para "limpiar bloat".
**Consecuencia**: lock EXCLUSIVE = downtime.
✅ `pg_repack` (si disponible) o ventana planeada.

### 36. Backups sin probar

❌ Backups corren, nadie restoreó nunca.
**Consecuencia**: día del desastre, descubrimos que están corruptos.
✅ DR drill mensual (`dr-drill-plan.md`).

### 37. Backups dentro del mismo provider

❌ Backups Render dentro de Render.
**Consecuencia**: outage Render = sin backup tampoco.
✅ Backups offsite cifrados (`backup-strategy.md`).

### 38. `pg_dump` desde producción en horario pico

❌ `pg_dump` peak hour.
**Consecuencia**: long-running tx, locks, CPU.
✅ Off-peak o read replica.

### 39. Tener `postgres` superuser para la app

❌ `DATABASE_URL=postgresql://postgres:...`.
**Consecuencia**: SQL injection → game over.
✅ Rol mínimo (`security-hardening.md`).

### 40. Permisos sobre `public` schema sin REVOKE

❌ Default postgres permite `CREATE` en `public` para PUBLIC.
**Consecuencia**: cualquier rol puede crear objetos.
✅ `REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT USAGE TO app;`.

### 41. No monitorear `n_dead_tup` ni autovacuum starvation

❌ Confiar 100% en autovacuum default.
**Consecuencia**: tablas con 80% bloat, queries lentas inexplicable.
✅ Monitor (`autovacuum-tuning.md`).

### 42. Connection pool por proceso × workers explota max_connections

❌ 8 gunicorn workers × 20 pool = 160 contra Render 97 limit.
**Consecuencia**: errors random.
✅ PgBouncer (`connection-pool.md`).

### 43. Log destructive queries en plain text

❌ `log_statement = 'all'` con `DELETE`/`UPDATE` que tienen PII.
**Consecuencia**: PII en logs.
✅ `log_statement = 'ddl'` + parametrización; audit table aparte.

## Data quality / multi-tenant

### 44. Queries cross-tenant "por accidente"

❌ Falta `WHERE company_id = ?` en endpoint compartido.
**Consecuencia**: leak grave.
✅ Capa repo central que **siempre** agrega filter + RLS.

### 45. Confiar en frontend para filtros de seguridad

❌ "El frontend manda company_id, confiamos".
**Consecuencia**: API trivial de explotar.
✅ Backend deriva `company_id` de la sesión, ignora cliente.

### 46. Timestamps sin timezone

❌ `created_at TIMESTAMP` (sin TZ).
**Consecuencia**: ambigüedad UTC vs local.
✅ Siempre `TIMESTAMPTZ`.

### 47. Edad calculada con `current_date - birth_date / 365.25`

❌ Inexacto, ignora leap years.
**Consecuencia**: errores +/- 1 año.
✅ `EXTRACT(YEAR FROM age(birth_date))`.

### 48. Comparar floats con `=`

❌ `WHERE price = 9.99`.
**Consecuencia**: 9.99 puede ser 9.9899999.
✅ Tipos `NUMERIC` para dinero/scores; `ABS(a-b) < eps` si no.

## Performance traps

### 49. `pg_stat_statements` desactivado / no usado

❌ Asumir que sabemos las queries lentas.
**Consecuencia**: optimizar lo equivocado.
✅ Habilitar + revisar weekly (`pgbadger` opcional).

### 50. Caché agresiva sin invalidación

❌ Cache 1h de queries que cambian cada minuto.
**Consecuencia**: data stale visible.
✅ TTL chico o invalidación por evento (CDC, NOTIFY).

### 51. JOIN sin entender selectividad

❌ JOIN entre tabla 10M y 50, planner usa nested loop bad.
**Consecuencia**: query 30min.
✅ ANALYZE actualizado; review plan.

### 52. ORM auto-load relations (eager) sin necesidad

❌ Cada `user.scans` carga 1000 scans.
**Consecuencia**: explode rows fetched.
✅ Lazy + explicit prefetch cuando necesario.

## Render-specific

### 53. Asumir `shared_preload_libraries` editable

❌ Pedir cualquier extensión sin chequear.
**Consecuencia**: falla al boot.
✅ Lista Render official.

### 54. Confiar 100% en backups Render

✅ Offsite (`backup-strategy.md`).

### 55. Conectar Render externo sin `sslmode=require`

❌ Connection plain.
**Consecuencia**: MITM, password leak.
✅ Forzar SSL.

## Tooling

### 56. ORM full sin entender SQL

❌ Programadores escriben ORM, nadie sabe leer EXPLAIN.
**Consecuencia**: bugs perf invisibles.
✅ Pair ORM con SQL literacy (`orm-evaluation.md`).

### 57. Test data 10 rows pero prod 10M

❌ Tests pasan rápido, prod muere.
**Consecuencia**: regression no detectada.
✅ Synthetic data realistic (`synthetic-data-generator.py`).

### 58. CI sin migrations test

❌ Migrations sólo se aplican en deploy.
**Consecuencia**: falla descubierta en prod.
✅ CI corre upgrade head + downgrade -1.

## Cheat-cheat sheet (ranking de gravedad)

| # | anti-pattern | severidad |
| --- | --- | --- |
| 6 | Falta company_id (multi-tenant) | P0 |
| 30 | ALTER COLUMN TYPE big table prod | P0 |
| 35 | VACUUM FULL prod | P0 |
| 36 | Backups sin probar | P0 |
| 39 | App como superuser | P0 |
| 14, 17 | Index inútil / N+1 | P1 |
| 18-22 | Query patterns slow | P1 |
| 26, 27, 28 | Tx problems | P1 |
| 31, 32 | Migration unsafe | P1 |
| 38, 40 | Op routine errors | P2 |
| 43, 45 | Security minor | P2 |
| resto | hygiene | P3 |

## Referencias

- `dba-runbook.md`
- `edge-cases-playbook.md` (#95)
- `security-hardening.md` (#108)
- `migration-tooling-deep.md` (#127)
- `cheatsheet.md` (#131)
