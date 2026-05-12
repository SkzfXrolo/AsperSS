# Connection lifecycle deep (Pack 48-H Round 4 · #112)

## Ciclo de vida completo

```
   App layer                          PgBouncer                          PostgreSQL
   ─────────                          ─────────                          ──────────
   1.  pool.acquire() ───►            checkout                ────►      assign server
   2.                                                                    AUTH (SCRAM)
   3.                                                                    SET application_name
   4.  set_local_tenant ─────────────────────────────────────►            SET LOCAL app.company_id
   5.  execute(SQL) ─────────────────────────────────────►                parse → plan → execute
   6.  commit ───────────────────────────────────────────►                COMMIT
   7.  pool.release() ────►          checkin (transaction end)
   8.                                                       ────►        RESET (if needed)
   9.                                                                    server idle → reused
   ...
   N.  server_lifetime ──►            evict ─────────────────►            DISCONNECT
```

## Etapas en detalle

### 1. App acquire (pool.checkout)

SQLAlchemy / driver tienen su propio pool **encima** de PgBouncer:

| Layer | Pool size típico | Latencia checkout |
| --- | --- | --- |
| SQLAlchemy | 5–10 por worker | <1ms |
| PgBouncer | 25 server conn | <5ms |
| PG real | n/a | n/a |

Si app pool agotado → wait queue → si timeout → `QueuePool limit exceeded`.

### 2. PgBouncer checkout

En `pool_mode=transaction`, PgBouncer asigna un server al primer SQL del cliente y libera al `COMMIT`/`ROLLBACK`. Esto multiplexa miles de clientes sobre decenas de server conn.

Estados visibles en `SHOW POOLS`:

| Estado | Significado |
| --- | --- |
| `cl_active` | clientes con server asignado |
| `cl_waiting` | clientes esperando server |
| `sv_active` | server ejecutando |
| `sv_idle` | server libre listo para reasignar |
| `sv_used` | server en transaction, vuelve al pool tras commit |

### 3. Auth (SCRAM-SHA-256)

Sólo ocurre cuando se crea una conexión NUEVA al server (PG). PgBouncer cachea credenciales; un checkout reusa.

**Costo de una auth fresca**: 20-50ms.
Por eso querés `pool_size` cubriendo el régimen estable, así rara vez se levanta una conexión nueva.

### 4. Set context (RLS, app_name, tenant)

Tras checkout, app debe setear contexto. Patrón recomendado:

```python
@app.before_request
def set_tenant_context():
    cid = current_user.company_id
    db.session.execute(text("SET LOCAL app.company_id = :v"), {"v": str(cid)})
    db.session.execute(text("SET LOCAL application_name = :v"), {"v": f"web/{request.endpoint}"})
```

**Importante**: `SET LOCAL` muere al `COMMIT`. Compatible con PgBouncer `transaction` mode.
`SET` (sin LOCAL) sobrevive y contamina la próxima sesión que reuse el server → 🐛 leak de tenant.

### 5. Execute (parse → plan → execute)

PG:

1. **Parse**: convertir SQL en parse tree.
2. **Rewrite**: aplicar reglas (views, RLS).
3. **Plan**: optimizador elige plan.
4. **Execute**: corre el plan, devuelve filas.

Prepared statements saltan parse/plan en repeticiones. PgBouncer `transaction` mode + prepared statements requiere PgBouncer ≥1.21 (PG14+).

### 6. Commit / Rollback

Al `COMMIT`:

- WAL flush al disco (sync replication: + replica).
- Locks liberados.
- PgBouncer marca server como reusable.

**Truco**: para writes batched, una sola transacción con muchos inserts amortiza el costo de fsync. `COMMIT` cada 1000 filas, no cada fila.

### 7. App release

SQLAlchemy devuelve la conexión al pool. `pool_pre_ping=True` ejecuta un `SELECT 1` al próximo checkout para detectar conexiones muertas.

### 8. Reset (transaction state)

PgBouncer corre `DISCARD ALL` o similar entre clientes si configurado (default OK para transaction mode).

### 9. Reuse / Evict

| Trigger | Acción |
| --- | --- |
| `server_lifetime` (default 3600s) | desconectar server, reduce leaks de memoria PG |
| `server_idle_timeout` (default 600s) | desconectar si no se usa |
| `pool_pre_ping` falla en app | descartar conexión del pool de app |
| TCP RST | descartar y reconnect transparente |

## Sobre prepared statements + PgBouncer

| Modo PgBouncer | Prepared OK? | Notas |
| --- | --- | --- |
| session | sí | 1-1 sin multiplexing |
| transaction (<1.21) | NO | desactivar prepared |
| transaction (≥1.21) + PG14+ | sí | usar `prepare_threshold=5` |
| statement | NO | inviable |

Para Argus: usar PgBouncer 1.21+ y aceptar prepared statements; si Render trae <1.21, configurar `prepared_statements=False` en SQLAlchemy.

## Stale connection detection

| Mecanismo | Capa | Cuándo |
| --- | --- | --- |
| `pool_pre_ping` | SQLAlchemy | antes de cada checkout |
| `keepalives_idle/interval/count` | TCP | conexiones idle largas |
| `pool_recycle` | SQLAlchemy | edad máxima conn |
| `tcp_keepalives_*` | PG server | TCP-level |
| `idle_in_transaction_session_timeout` | PG server | corta idle in tx |

Combinación recomendada Argus:

```python
engine = create_engine(
    url,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=1800,             # 30 min
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
        "options": "-c statement_timeout=30000 -c lock_timeout=5000",
    },
)
```

## Errores típicos y diagnóstico

| Error | Causa común |
| --- | --- |
| `QueuePool limit of size X overflow Y reached` | pool agotado; aumentar o investigar leaks |
| `OperationalError: server closed the connection unexpectedly` | restart PG o NAT cierra conn idle |
| `psycopg2.errors.AdminShutdown` | server reiniciado / failover |
| `FATAL: sorry, too many clients` | PgBouncer no levantó / cap PG llegó |
| `Connection refused` | Red / DNS / Render down |

## Métricas (mínimo a alertar)

```sql
-- en PG
SELECT state, COUNT(*) FROM pg_stat_activity GROUP BY 1;
SELECT count(*) FROM pg_stat_activity WHERE state='idle in transaction';

-- en PgBouncer (psql al puerto admin)
SHOW POOLS;
SHOW STATS;
SHOW CLIENTS;
SHOW SERVERS;
```

| Alerta | Threshold |
| --- | --- |
| cl_waiting > 0 | sostenido 1min |
| sv_active > 90% pool_size | sostenido 5min |
| idle in tx > 5min | inmediato (probable bug app) |
| pool_pre_ping failures | >5/min |

## Anti-patterns

1. ❌ Abrir conn por request HTTP sin pool.
2. ❌ `SET` (sin LOCAL) en transaction mode → leak entre tenants.
3. ❌ `pool_recycle=0` (nunca recicla) → conn vieja con state corrupto.
4. ❌ Tx abiertas con `BEGIN` y nunca `COMMIT` (web handler con exception sin rollback).
5. ❌ `autocommit=False` por default + commit manual olvidado.

## Referencias

- `connection-pool.md` — config PgBouncer + SQLAlchemy.
- `statement-timeout.md` — timeouts por capa.
- `security-hardening.md` — roles + RLS context.
