# Statement timeout tuning (Pack 48-H Round 4 · #111)

## Por qué importa

Sin timeouts, una query mal escrita puede consumir CPU del primario durante minutos, bloquear locks, llenar `pg_stat_activity` y dejar al pool sin conexiones libres. Para un SaaS multi-tenant, una sola query lenta de un cliente puede dañar a todos.

## Tres timeouts complementarios

| Parámetro | Qué corta | Uso típico |
| --- | --- | --- |
| `statement_timeout` | tiempo de ejecución de un statement | proteger contra runaway queries |
| `lock_timeout` | tiempo esperando un lock | proteger contra `ALTER TABLE` que se cuelga |
| `idle_in_transaction_session_timeout` | tiempo idle dentro de tx abierta | proteger contra conexiones zombi |

## Defaults recomendados para Argus

### Globalmente (en `postgresql.conf` o `ALTER SYSTEM`)

```sql
ALTER SYSTEM SET statement_timeout                        = '30s';
ALTER SYSTEM SET lock_timeout                             = '5s';
ALTER SYSTEM SET idle_in_transaction_session_timeout      = '60s';
SELECT pg_reload_conf();
```

### Por rol

```sql
-- web app: queries deben ser rapidísimas
ALTER ROLE app                SET statement_timeout = '5s';
ALTER ROLE app                SET lock_timeout      = '1s';

-- read-only / panel staff: tolera 30s
ALTER ROLE app_ro             SET statement_timeout = '30s';

-- workers / cron: 5 min
ALTER ROLE worker             SET statement_timeout = '300s';

-- DBA: sin timeout
ALTER ROLE dba                SET statement_timeout = '0';

-- reportes / analytics: 2 min
ALTER ROLE analyst            SET statement_timeout = '120s';
```

### Por endpoint (app)

```python
# patrón recomendado: SET LOCAL dentro de una transacción
with db.session.begin():
    db.session.execute(text("SET LOCAL statement_timeout = '60s'"))
    result = db.session.execute(text(slow_report_sql))
```

`SET LOCAL` solo aplica a la transacción actual; no contamina la conexión.

## Tabla de timeouts por caso de uso

| Caso | statement_timeout | lock_timeout | Notas |
| --- | --- | --- | --- |
| Login / auth | 3s | 1s | si supera, page |
| Dashboard ligero | 5s | 1s | cae rápido si pasa |
| Dashboard heavy | 15s | 2s | reportes paneles |
| Reporte mensual | 60s | 5s | corre off-peak |
| ETL stage | 300s | 30s | nightly |
| Migration (DDL) | 30s | 5s | si lock no llega, abortar y reprogramar |
| `pg_dump` | 0 (sin límite) | 0 | en ventana |
| Backfill batched | 60s | 5s | por batch |

## Cómo aplicarlo en código sin tocar `app.py` ahora

Spec para subagente D. El patrón:

```python
def with_timeout(seconds):
    """Decorator que envuelve la sesión SQLAlchemy con SET LOCAL statement_timeout."""
    def decorator(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            with db.session.begin():
                db.session.execute(text(f"SET LOCAL statement_timeout = '{seconds}s'"))
                return fn(*args, **kwargs)
        return inner
    return decorator

@app.route('/api/reports/monthly')
@with_timeout(60)
def monthly_report():
    ...
```

## Qué pasa cuando timeout dispara

PG aborta el statement con:

```
ERROR: canceling statement due to statement timeout
SQLSTATE: 57014  (query_canceled)
```

App debe:

1. Capturar `SQLSTATE 57014` específicamente.
2. NO reintentar automático (probablemente fallaría igual; mejor exponer error al usuario).
3. Loggear con `application_name` para diagnóstico.
4. Devolver `HTTP 504 Gateway Timeout` con mensaje friendly.

```python
except psycopg2.errors.QueryCanceled as e:
    log.warning("query_timeout", endpoint=request.path)
    return jsonify({"error": "timeout"}), 504
```

## Lock_timeout: caso especial migrations

Migrations DDL pueden quedar bloqueadas esperando un lock exclusivo si hay una transacción de larga duración (cron, reporte). Sin `lock_timeout`, la migration se cuelga indefinidamente; con él, falla en X segundos y se puede reintentar.

```sql
-- en cada migration Alembic / runbook:
BEGIN;
  SET LOCAL lock_timeout = '5s';
  SET LOCAL statement_timeout = '30s';
  ALTER TABLE scans ADD COLUMN company_id INTEGER;
COMMIT;
```

Si falla `lock_timeout`: detectar tx ofensora, terminarla, reintentar.

## idle_in_transaction_session_timeout

Detecta conexiones que abrieron `BEGIN` y se "olvidaron" de cerrar (típico con clientes Postgres en sleep, debug, o un cuelgue del app server).

- `60s` es razonable para Argus.
- Cuando dispara: PG cierra la conexión (no sólo cancela). El cliente debe reconectar.

## Métricas a monitorear

```sql
-- queries activas que pasaron timeout (raras; PG aborta antes)
SELECT pid, NOW() - query_start AS age, state, query
FROM pg_stat_activity
WHERE state = 'active' AND NOW() - query_start > INTERVAL '30 seconds';

-- contar QueryCanceled del último día (requiere log_min_messages=warning)
-- grep en pg_log: count by application_name
```

## Anti-patterns

1. ❌ `statement_timeout = 0` (sin límite) en producción.
2. ❌ Setear timeouts globales muy altos (>1min) por miedo a romper algo.
3. ❌ Reintentar automático tras timeout sin backoff.
4. ❌ Ignorar `query_canceled` en código (loggea como error genérico).
5. ❌ `SET statement_timeout` sin `LOCAL` (contamina conexión que vuelve al pool).

## Adopción

1. Pack 49: aplicar timeouts por rol via `ALTER ROLE`.
2. Pack 49: handler de `query_canceled` en `app.py` (subagente D).
3. Pack 50: decorator `with_timeout` para endpoints específicos.
4. Pack 50: alertas en `pg_stat_statements` para queries que se cancelan con frecuencia.

## Referencias internas

- `edge-cases-playbook.md` (long-running queries)
- `migration-runbook.md` (lock_timeout en DDL)
- `connection-pool.md` (pool semantics)
