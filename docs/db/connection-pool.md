# Argus Projects — Connection pool optimization (Pack 48-H Round 3 · #91)

## Diagnóstico actual

- Flask + gunicorn (n workers) + SQLAlchemy → cada worker abre su pool propio.
- Render PG tier "Basic" ~22 connections, "Standard" ~97, "Pro" ~197.
- Si gunicorn workers=4 × pool_size=10 = **40 conexiones**, ya pasa el límite del tier Basic.
- Picos cortos (e.g. cron interno + tráfico web) generan `FATAL: too many connections`.

## Recomendación: introducir PgBouncer

PgBouncer en modo **transaction pooling** multiplexa N conexiones de app sobre M conexiones reales (M << N), liberando la conexión al DB en cuanto la transacción cierra.

```
[Flask/SQLAlchemy] ──► [PgBouncer (1k client conn)] ──► [Postgres (25 server conn)]
```

## Modos disponibles (no todos seguros para SQLAlchemy)

| Modo | Compatible con SQLAlchemy default | Notas |
| --- | --- | --- |
| `session` | ✅ | 1 a 1, sin beneficio real. |
| `transaction` | ⚠️ | Best balance. **Prohibido** usar SET, advisory locks largos, prepared statements. |
| `statement` | ❌ | Rompe transacciones; no usar. |

Para `transaction`:
- Desactivar prepared statements: `prepared_statements=False` en `create_engine`.
- O usar PG14 + PgBouncer 1.21+ con `server_reset_query` y prepared statements habilitados.

## Configuración propuesta

### `pgbouncer.ini` (ver `scripts/db/pgbouncer.ini`)

| Parámetro | Valor recomendado | Justificación |
| --- | --- | --- |
| `pool_mode` | `transaction` | Mejor multiplexing. |
| `max_client_conn` | `1000` | Headroom para crecimiento. |
| `default_pool_size` | `25` | <=80% del límite del tier. |
| `min_pool_size` | `5` | Warm connections. |
| `reserve_pool_size` | `5` | Buffer ante picos. |
| `server_idle_timeout` | `600` | Reciclar tras 10min idle. |
| `server_lifetime` | `3600` | Reciclar conexiones cada hora. |
| `query_wait_timeout` | `120` | Timeout si cola explota. |

### SQLAlchemy (capa app)

```python
engine = create_engine(
    DATABASE_URL,
    pool_size=5,            # bajo, porque PgBouncer multiplexa
    max_overflow=5,
    pool_pre_ping=True,     # detectar conexiones muertas
    pool_recycle=1800,      # 30min, debajo del server_lifetime de PgBouncer
    connect_args={
        "prepare_threshold": None,   # asyncpg/psycopg3
        "options": "-c statement_timeout=30000",
    },
)
```

> NOTA: **no** modificar `app.py` en este Round. Esto queda como spec para subagente D / dev.

## Métricas para alertar

| Métrica | Query | Umbral page |
| --- | --- | --- |
| Active server conn | `SHOW POOLS` PgBouncer | >80% pool size |
| Client wait | `SHOW POOLS .cl_waiting` | >0 sostenido 5min |
| Failed logins | logs PgBouncer | >5/min |
| Idle in tx | `pg_stat_activity` | >10s |
| Connection eviction | PgBouncer logs | cualquier ráfaga |
| Conexiones totales PG | `SELECT count(*) FROM pg_stat_activity` | >90% tier limit |

## Render specifics

- Render permite addons. Si **no** ofrece PgBouncer managed, levantar PgBouncer como **proceso adicional** en el container app o servicio sidecar.
- Si Render bloquea sockets internos: usar PgBouncer **dentro** del web service, escuchando localhost:6432.
- `DATABASE_URL` interno = `postgres://app:***@localhost:6432/argus`.
- Variable externa para mantenimiento directo a primario sin pasar por PgBouncer.

## Trade-offs

| Issue | Workaround |
| --- | --- |
| Prepared statements requieren ajustes | Disable o usar `prepare_threshold=None` (psycopg3). |
| Advisory locks no sobreviven transacción en transaction mode | Cambiar a session mode para esa conexión específica (separate engine). |
| Single point of failure | Correr 2 instancias detrás de un VIP / Render auto-restart. |
| Debug más complejo (PID de PG ≠ PID de app) | Habilitar `application_name` y `log_line_prefix=%a`. |

## Rollout

1. Levantar PgBouncer en staging, mismo límite que prod.
2. Pasar 100% del tráfico a PgBouncer 24h, observar `SHOW POOLS`.
3. Tunear `default_pool_size` y `reserve_pool_size`.
4. Producción: rolling deploy (un worker a la vez apunta a 6432).
5. Mantener fallback `DATABASE_URL_DIRECT` para emergencias.

## Referencias internas

- `docs/db/dba-runbook.md` — procedimientos VACUUM/REINDEX.
- `docs/db/cost-optimization.md` — tiers de Render.
- `docs/db/read-replicas-design.md` — read replicas también pasan por PgBouncer.
