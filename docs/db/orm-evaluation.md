# ORM evaluation (Pack 48-H Round 4 · #124)

## Estado actual

`web_app/app.py` usa SQL **raw** (string templates con `_PH` placeholder para PG/SQLite). No hay ORM ni schema mapping en Python.

Pros del estado actual:

- Cero abstracción → cero "magic".
- SQL es lo que vemos.
- Bajo overhead.

Contras:

- Boilerplate enorme: `dict(zip(cur.description, row))` repetido.
- Sin type safety: typo en nombre de columna sólo aparece en runtime.
- Migraciones manuales (problema F-001).
- Lógica de queries dispersa en routes.
- Difícil de testear (mocks de cur/conn).

## Candidatos

### A) **SQLAlchemy 2.0** (Core + opcional ORM)

- API más madura del ecosistema Python.
- Soporta async (asyncio).
- "Core" expone Table objects + queries fluentes; "ORM" agrega clases mapped.
- Alembic generado a partir de los models.

**Pro Argus**: comunidad enorme, doc, stable. Async opcional.
**Contra**: curva, escribe más código en Core que en raw SQL si la query es trivial.

### B) **Peewee**

- ORM más simple y compacto.
- Migrations built-in.

**Pro**: fácil de empezar.
**Contra**: comunidad chica, menos features para casos avanzados.

### C) **Tortoise** (async-first)

- Inspirado en Django ORM, asyncio nativo.

**Pro**: ergonómico si app pasa a async.
**Contra**: relativamente joven, menos battle-tested.

### D) **SQLModel** (Pydantic + SQLAlchemy)

- Mismo modelo Pydantic sirve para validación + DB + JSON.

**Pro**: type hints como source of truth.
**Contra**: SQLAlchemy underneath; misma curva.

### E) **psycopg + dataclasses** ("ORM-lite manual")

Patrón: dataclass por tabla, función `from_row(cls, row)` y `INSERT/UPDATE` ad-hoc.

**Pro**: cero magic, todo explícito.
**Contra**: reinventa SQLAlchemy a escala.

## Recomendación: SQLAlchemy 2.0 (Core, no ORM)

Razones:

1. **Type safety** en queries vía `mapped_column` y `Mapped[]`.
2. **Compat PG/SQLite** sin `_PH` hack.
3. **Alembic** auto-generate migrations.
4. **Async** opcional con `AsyncEngine`.
5. **Composabilidad**: queries como objetos.
6. Cumple con el principio de Argus: SQL visible, no objetos magicos.

Evitar ORM completo (clases mapped + lazy loading) en Pack 49. Si más tarde se necesita relaciones, agregar incrementalmente.

## Migration plan (alto nivel, dev=D)

### Fase 1: paralelo (Pack 49)

- Crear `web_app/models.py` con tabla objects:

```python
from sqlalchemy import Table, Column, Integer, String, TIMESTAMP, MetaData

metadata = MetaData()

scans = Table(
    "scans", metadata,
    Column("id", Integer, primary_key=True),
    Column("token_id", Integer),
    Column("company_id", Integer),
    Column("started_at", TIMESTAMP),
    # ...
)
```

- Bootstrap Alembic (ver `alembic-bootstrap.md` Round 2).
- Mantener queries existentes raw.

### Fase 2: migrar endpoint por endpoint (Pack 50-52)

```python
# antes
cur.execute("SELECT id, verdict FROM scans WHERE company_id = ?", (cid,))

# después
result = db.execute(select(scans.c.id, scans.c.verdict).where(scans.c.company_id == cid))
```

Tests pasan en cada PR. No "big bang".

### Fase 3: type checking (Pack 53+)

- Activar `mypy --strict` solo en `web_app/models.py`.
- Resto de la app gradual.

### Fase 4: revisar relations (Pack 60+)

- Si hay >5 N+1 detectados, agregar relationships ORM.
- Antes, dataloader pattern (ver `graphql-layer.md` #125).

## Migration risks

| Riesgo | Mitigación |
| --- | --- |
| Performance regression con ORM lazy load | Core only; explicit JOIN |
| `_PH` placeholder específico de Argus | SQLAlchemy maneja PG/SQLite nativamente |
| Tests que parsean SQL hardcoded | actualizar tests gradual |
| `app.py` mezcla queries de distintos dominios | refactor en `repo/*.py` modules durante migración |

## Performance benchmarks

| Operación | Raw psycopg | SQLAlchemy Core | SQLAlchemy ORM |
| --- | --- | --- | --- |
| INSERT 1 row | 100% | 95-100% | 85-90% |
| SELECT 100 rows | 100% | 95% | 80% |
| SELECT 1000 rows | 100% | 90% | 70% |

Para Argus, latencia DB ya domina sobre overhead Python; el ORM cost es secundario.

## Async vs sync

- Hoy: Flask sync.
- Si app pasa a async (FastAPI / Quart): SQLAlchemy 2.0 async funciona.
- Si no: dejar sync.

No forzar async en Pack 49.

## Decisión

**Adoptar SQLAlchemy 2.0 (Core) en Pack 49**, junto con Alembic. Migración gradual endpoint-por-endpoint. Sin ORM mapping completo hasta que el dolor lo justifique.

Riesgo principal: tener que reescribir tests; bloque incremental aceptable.

## Anti-patterns a evitar

1. ❌ Mezclar ORM y raw SQL en el mismo endpoint sin razón.
2. ❌ Usar `lazy='dynamic'` en colecciones grandes (N+1 oculto).
3. ❌ Confiar en `Model.query.filter_by(...)` con strings de columna (no type-safe).
4. ❌ Migrations auto-generadas sin revisar (Alembic siempre necesita review humano).

## Referencias

- `alembic-bootstrap.md` (Round 2).
- `migration-tool-comparison.md` (Round 2).
- `schema-versioning.md` (#99).
- SQLAlchemy 2.0 docs.
