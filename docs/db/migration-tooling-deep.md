# Migration tooling deep (Pack 48-H Round 4 · #127)

Profundización sobre Alembic (la tool recomendada en `migration-tool-comparison.md` Round 2). Branches, merges, downgrades, auto-generation, patrones production-safe.

## Setup mínimo

```bash
pip install "alembic>=1.13"

alembic init -t async migrations    # o sync, según app
# config: edit alembic.ini → sqlalchemy.url = ${DATABASE_URL}
# alembic/env.py: import models metadata; target_metadata = models.metadata
```

Ver `alembic-bootstrap.md` (Round 2).

## Estructura del repo

```
migrations/
├── env.py                 ← conexión + import metadata
├── script.py.mako         ← template
└── versions/
    ├── 2026_05_12_1342-a1b2c3d4_baseline.py
    ├── 2026_05_15_1010-e5f6g7h8_add_company_id_to_scans.py
    └── ...
```

Convención de nombres: `YYYY_MM_DD_HHMM-<revid>_<verb>_<subject>.py`.

## Comandos diarios

| Acción | Comando |
| --- | --- |
| Ver state actual | `alembic current` |
| Ver historia | `alembic history --indicate-current` |
| Crear migration vacía | `alembic revision -m "add company_id to scans"` |
| Auto-generar | `alembic revision --autogenerate -m "..."` |
| Aplicar | `alembic upgrade head` |
| Rollback uno | `alembic downgrade -1` |
| Aplicar uno específico | `alembic upgrade +1` |
| Marcar como aplicada sin correr | `alembic stamp head` |

## Branches y merges

Cuando dos PRs paralelas crean migrations:

```
main:  abc1 → abc2
         │
         ├── PR1: abc2 → ddd1
         └── PR2: abc2 → eee1
```

Al mergear ambas:

```bash
alembic merge -m "merge ddd1 + eee1" ddd1 eee1
# crea fff1 con down_revision = (ddd1, eee1)
```

Alembic resuelve dependencias.

Mejor práctica: **prevenir** branches manteniendo PRs cortas y mergeo frecuente. Si hay branch frecuente, agregar bot check que detecte multi-head.

## Auto-generation: limitaciones

`autogenerate` compara metadata de SQLAlchemy contra DB live. Funciona bien para:

- CREATE/DROP TABLE
- ADD/DROP COLUMN (tipo simple)
- CREATE/DROP INDEX (sólo declarativo en model)

**No detecta**:

- Renombrados (los ve como drop + add).
- Cambios de tipo "compatibles" (varchar(50) → varchar(100)).
- Cambios de defaults (a veces).
- Constraints CHECK custom.
- Triggers / funciones PL/pgSQL.
- Permisos / RLS policies.

→ siempre **review humano** del archivo generado antes de commitear.

## Manual review checklist

Por cada migration:

- [ ] `upgrade()` y `downgrade()` ambos implementados.
- [ ] `op.execute(...)` raw SQL → quote correcto, parámetros seguros.
- [ ] DDL con `IF NOT EXISTS` o `IF EXISTS` donde aplique.
- [ ] `CREATE INDEX CONCURRENTLY` para tablas grandes en prod.
- [ ] `SET LOCAL lock_timeout` en cada DDL.
- [ ] Si data backfill: en batches (no UPDATE 10M rows).
- [ ] Tests pasan en CI.
- [ ] Doc en `migration-runbook.md` si requiere ventana.

## Production-safe migration patterns

### Patrón 1 · Add nullable column

```python
def upgrade():
    op.add_column("scans", sa.Column("company_id", sa.Integer(), nullable=True))
    # crear índice CONCURRENTLY en una migration aparte para evitar bloqueo
def downgrade():
    op.drop_column("scans", "company_id")
```

Aplicar también un índice **en otra migration** con `op.create_index(..., postgresql_concurrently=True)`.

### Patrón 2 · Hacer NOT NULL una columna existente (backfill + cutover)

Tres pasos en migrations separadas:

1. **Add column nullable** + backfill batched.
2. **App app cambia para escribir siempre el valor**.
3. **ALTER COLUMN ... SET NOT NULL** + `ADD CONSTRAINT chk_x NOT VALID;` después `VALIDATE CONSTRAINT;` (evita full scan en lock).

### Patrón 3 · Renombrar columna (dual-write)

| Paso | Migration | App release |
| --- | --- | --- |
| 1 | add `new_name`, trigger sync old→new | deploy: writes a ambos |
| 2 | backfill old→new | — |
| 3 | reads switch a new_name | — |
| 4 | drop trigger, drop `old_name` | — |

### Patrón 4 · Drop column

| Paso | Acción |
| --- | --- |
| 1 | App deja de leer/escribir la col |
| 2 | Esperar al menos 1 release que app no usa |
| 3 | `ALTER TABLE ... DROP COLUMN ...` |

Nunca drop columns en el mismo deploy que las deja de usar.

### Patrón 5 · Cambio de tipo

Para tipos compatibles (`varchar(N) → varchar(M)`): un solo ALTER, rápido.

Para tipos incompatibles (`varchar → uuid`): patrón dual-column igual que rename.

### Patrón 6 · Add CHECK constraint sin lock largo

```sql
ALTER TABLE scans ADD CONSTRAINT chk_score CHECK (risk_score BETWEEN 0 AND 100) NOT VALID;
-- backfill: ya están en rango
ALTER TABLE scans VALIDATE CONSTRAINT chk_score;  -- scan rápido, lock SHARE
```

### Patrón 7 · CREATE INDEX en tabla grande

```python
def upgrade():
    op.execute("COMMIT")  # CONCURRENTLY no acepta tx
    op.create_index("idx_x", "scans", ["company_id"], postgresql_concurrently=True)
def downgrade():
    op.execute("COMMIT")
    op.drop_index("idx_x", postgresql_concurrently=True)
```

Requisito en Alembic: `transactional_ddl = False` en env.py para esa migration.

## Testing migrations en CI

Patrón mínimo (Github Actions / similar):

```yaml
services:
  postgres:
    image: postgres:16
    env: { POSTGRES_PASSWORD: pw }
    ports: ["5432:5432"]

steps:
  - run: pip install -e .
  - run: alembic upgrade head
  - run: pytest tests/db
  - run: alembic downgrade -1
  - run: alembic upgrade head           # re-apply (idempotency)
```

Falla si:

- migration tarda >60s.
- downgrade rompe.
- re-apply no es idempotente.

## Coexistir con `_plugin_schema_guard` legacy

Argus tiene funciones tipo `_plugin_schema_guard()` que ejecutan `CREATE TABLE IF NOT EXISTS` en boot. Plan de coexistencia con Alembic:

1. **Pack 49**: Alembic toma ownership; el `schema_guard` se mantiene como fallback.
2. **Pack 50**: marcar deprecated; warning si falta una tabla esperada.
3. **Pack 52**: borrar `schema_guard`.

Si una nueva tabla nace post-Alembic, **no** agregar a `schema_guard`; toda nueva tabla vía migration.

## Rollback rules

| Tipo de cambio | Downgrade seguro? |
| --- | --- |
| add column nullable | sí (drop) |
| add column NOT NULL with default | sí (drop) |
| drop column | NO sin restore (data perdida) |
| rename column | sí (rename back) si no hubo writes |
| add index | sí (drop) |
| drop index | sí (recreate) |
| add table | sí (drop) |
| drop table | NO sin restore |
| backfill data | parcial; requiere backup |

Migrations que destruyen data **deben** documentar que downgrade no es posible sin backup.

## Bloqueantes en producción

| Operación | Lock | Acción |
| --- | --- | --- |
| `ADD COLUMN` (nullable, sin default) | corto (ms) | OK online |
| `ADD COLUMN` con default const (PG11+) | corto | OK |
| `ADD COLUMN` con default volátil (`NOW()`) | full rewrite | ventana |
| `DROP COLUMN` | corto | OK |
| `ALTER COLUMN TYPE` (compatible) | full table rewrite | ventana |
| `CREATE INDEX` | bloquea writes | usar `CONCURRENTLY` |
| `ADD FOREIGN KEY` | requiere SHARE lock + scan | usar `NOT VALID` + `VALIDATE` |
| `ALTER TABLE SET NOT NULL` | SHARE lock + scan | usar CHECK constraint NOT VALID antes |

## Versionado de migrations (relacionado a `schema-versioning.md` #99)

Cada migration tiene `revision` (hash) + `down_revision`. Para humanos, tag opcional en mensaje: `[v0.49.0]`.

## Anti-patterns

1. ❌ `op.execute("UPDATE big_table SET ...")` sin batches.
2. ❌ Migrations >5 min en producción sin ventana.
3. ❌ `autogenerate` y commit sin revisar.
4. ❌ Migrations que dependen de data específica de prod ("hardcoded id 42").
5. ❌ Multi-head dejados sin merge.
6. ❌ Editar revisión ya aplicada en producción.

## Tooling complementario

| Tool | Propósito |
| --- | --- |
| `alembic-utils` | manejar funciones/triggers/views PG declarativamente |
| `sqlalchemy-utils` | tipos extra (UUIDType, EmailType) |
| `pg_diff` | comparar dos DBs |
| `tbls` | doc auto-generada del schema |
| `squawk` | linter de DDL "production-unsafe" |

## Roadmap Argus

| Pack | Acción |
| --- | --- |
| 49 | bootstrap Alembic, baseline migration |
| 49 | aplicar F-001 (add `scans.company_id`) como primera migration real |
| 50 | CI gate con `squawk` |
| 51 | adoptar `alembic-utils` para funciones (#120) y triggers |
| 52 | drop `_plugin_schema_guard` legacy |

## Referencias

- `migration-tool-comparison.md` (Round 2)
- `alembic-bootstrap.md` (Round 2)
- `migration-runbook.md`
- `schema-versioning.md` (#99)
- `testing-strategies.md` (#123)
