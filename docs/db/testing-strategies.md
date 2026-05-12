# DB testing strategies (Pack 48-H Round 4 · #123)

## Niveles de testing

| Nivel | Qué valida | Herramienta sugerida |
| --- | --- | --- |
| **Schema** | shape esperado (cols, tipos, índices, FKs) | golden + drift check (#100/#103) |
| **Data** | invariantes (no leaks, no orphans, no NULL en NOT NULL) | `integrity-checks.sql`, `data-quality.sql` (Round 1/2) |
| **Migration** | upgrade + downgrade idempotente, sin lock largo | Alembic en DB efímera |
| **Performance** | plan estabilidad y latencia regresiones | `bench/*` (#128) |
| **Function/Trigger** | comportamiento PL/pgSQL | pgTAP / plpgunit |
| **End-to-end** | flujo app + DB | pytest + DB efímera |

## Stack recomendado para Argus

| Tipo | Tool |
| --- | --- |
| Unit funcs/triggers | pgTAP (sintaxis SQL, output TAP) |
| Integration app+DB | pytest + `testcontainers-postgres` |
| Schema golden | `schema-drift-check.py` (#100) en CI |
| Migration tests | Alembic + DB efímera + assertions |
| Perf | pgbench + `bench/run-bench.sh` (#128) |

## Schema tests (golden diff)

Cada PR que toca migrations dispara:

```yaml
# .github/workflows/db.yml (concepto)
- run: docker run -d -p 5432:5432 postgres:16
- run: alembic upgrade head
- run: pg_dump --schema-only --no-owner ... > /tmp/actual.sql
- run: python scripts/db/schema-drift-check.py
      --db-url $TEST_URL --expected scripts/db/golden-schema.json
```

Falla si hay drift inesperado.

## Data tests (invariants)

Lista actual:

- `integrity-checks.sql` — 25 invariantes core.
- `data-quality.sql` — 20 invariantes extra.
- `tenant-isolation-checks.sql` — 15 multi-tenant.

Patrón:

```sql
-- expectativa: 0 filas
SELECT COUNT(*) AS alert_XX_description
FROM table WHERE invariante_roto;
```

Wrappear en pytest:

```python
@pytest.fixture
def seeded_db(): ...

def test_no_orphan_violations(seeded_db):
    cur = seeded_db.cursor()
    cur.execute("SELECT COUNT(*) FROM plugin_violations v WHERE NOT EXISTS (SELECT 1 FROM scans s WHERE s.id=v.scan_id)")
    assert cur.fetchone()[0] == 0
```

Ejecutar todos los `.sql` en orden y reportar.

## Migration tests

Para cada nueva migration:

1. **Up dry-run**: aplicar a snapshot de prod (anonimizado, ver `synthetic-data-generator.py`).
2. **Up timing**: medir locks y duración; falla si lock_time > 5s.
3. **Down**: aplicar `alembic downgrade -1`; data debe quedar coherente.
4. **Re-up**: aplicar de nuevo; idempotencia.
5. **Stats**: `ANALYZE` no debe explotar.

```python
def test_migration_safe(alembic_engine):
    alembic_command.upgrade(cfg, "head")
    # assert no lock left
    cur = alembic_engine.execute("SELECT count(*) FROM pg_locks WHERE granted=false")
    assert cur.scalar() == 0
```

## Performance tests

`bench/run-bench.sh` produce JSON. Comparar con baseline:

```python
def test_query_latency_p95():
    out = subprocess.run(["./run-bench.sh", "select"], capture_output=True)
    data = json.loads(out.stdout)
    baseline = json.load(open("baselines/select.json"))
    assert data["p95_ms"] <= baseline["p95_ms"] * 1.2, "regression"
```

Tolerancia 20% por defecto.

## pgTAP

```sql
-- tests/db/pgtap/test_argus_functions.sql
BEGIN;
SELECT plan(3);
SELECT is(argus_score_to_level(85), 'CRITICAL', 'CRITICAL band');
SELECT is(argus_score_to_level(50), 'MID',      'MID band');
SELECT is(argus_anonymize_ip('192.168.1.42'::inet), '192.168.1.0/24'::inet);
SELECT * FROM finish();
ROLLBACK;
```

Correr con `pg_prove tests/db/pgtap/*.sql`.

## pytest fixtures sugeridas

```python
# conftest.py (futuro)
import pytest
import testcontainers.postgres

@pytest.fixture(scope="session")
def pg_container():
    with testcontainers.postgres.PostgresContainer("postgres:16") as pg:
        yield pg

@pytest.fixture
def seeded_db(pg_container):
    # ejecutar migrations + seed-data.sql
    ...
    yield db
```

## CI / Pipeline

Bloqueante (debe pasar para merge):

- Schema golden diff (sólo si tocó migrations).
- Integrity checks (todos en 0 alerts).
- Migration up/down idempotente.
- Unit pgTAP de funciones.

No-bloqueante (informa pero no rompe):

- Performance regression (degradación >20% comentada en PR).
- Bloat trend.

## Manual tests en staging pre-deploy

Checklist:

- [ ] `pg_dump --schema-only` igual entre staging y producción (post-migration).
- [ ] App smoke: login + create scan + view dashboard.
- [ ] Replication lag < 5s.
- [ ] `pg_stat_user_tables.last_analyze` reciente.

## Anti-patterns

1. ❌ Tests que dependen del estado de prod data.
2. ❌ "Fast tests" que saltean migrations (compatibility break silencioso).
3. ❌ Mocks de DB tan elaborados que terminan reimplementando PG.
4. ❌ Tests que crean/dropean tablas en DB compartida (race conditions).
5. ❌ Asumir orden de filas sin `ORDER BY`.

## Roadmap

| Pack | Acción |
| --- | --- |
| 49 | Conftest pytest + testcontainers |
| 49 | Job CI con schema-drift-check |
| 50 | pgTAP para funciones (`#120`) |
| 51 | Benchmark suite en CI nightly |
| 52 | Migration testing automático |
| 53 | Mutation testing data invariants |

## Referencias

- `golden-tests.md` (#103)
- `schema-drift-detection.md` (#100)
- `bench/*` (#128)
- Round 1: `integrity-checks.sql`, `data-quality.sql`.
