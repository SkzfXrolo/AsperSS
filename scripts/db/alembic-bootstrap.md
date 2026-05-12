# Bootstrap Alembic — Argus Projects (Pack 48-H Round 2)

> **No ejecutado en este repo** — guía para el equipo cuando decidan adoptar migraciones formales.
> Scope permitido del subagente: sólo este archivo en `scripts/db/`. El código `alembic.ini` / `migrations/` lo crea el owner al aplicar.

## 1. Instalación local

```bash
cd web_app   # o raíz según estructura elegida
python -m pip install "sqlalchemy>=2" alembic psycopg2-binary
```

## 2. Inicializar

```bash
alembic init migrations
```

Editar `alembic.ini`:

- `sqlalchemy.url = driver://user:pass@host/dbname` **o** mejor: leer de `os.environ["DATABASE_URL"]` en `env.py`.

## 3. Baseline sin tocar datos existentes

En la base **ya poblada** de producción:

```bash
# Crear revisión vacía que representa "estado actual"
alembic revision -m "baseline_pack48_current_schema"

# Marcar como aplicada sin ejecutar SQL
alembic stamp head
```

A partir de aquí, cada PR añade `alembic revision -m "add scans company_id"` con `op.add_column(...)`.

## 4. Primera migración real sugerida (F-001)

Contenido conceptual (el fix lo implementa el dev D):

```python
def upgrade():
    op.add_column('scans', sa.Column('company_id', sa.Integer(), nullable=True))
    op.create_index('idx_scans_company_started', 'scans', ['company_id', sa.text('started_at DESC')], postgresql_ops={'started_at': 'DESC NULLS LAST'})
    # op.execute("UPDATE scans SET company_id = ... FROM scan_tokens ...")

def downgrade():
    op.drop_index('idx_scans_company_started')
    op.drop_column('scans', 'company_id')
```

## 5. CI

```yaml
# GitHub Actions (ejemplo)
- run: alembic upgrade head
  env:
    DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}
```

## 6. SQLite local

Opciones:

- **A)** Rama de revisiones separada `sqlite/` (duplicación mala).
- **B)** Misma revisión con `if context.is_offline_mode():` NO — mejor detectar dialect en `env.py` y `batch_alter_table` para SQLite.

## 7. Convención de nombres

`YYYYMMDD_packNN_short_description`
