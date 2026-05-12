# Argus Projects — Read replicas strategy (Pack 48-H Round 2)

## Cuándo introducir read replica

| Señal | Umbral sugerido | Acción |
| --- | --- | --- |
| Ratio lecturas/escrituras | **> 10:1** sostenido 7 días (`pg_stat_database` tup_returned / tup_fetched vs inserts) | Evaluar replica |
| Latencia p95 | **> 100 ms** en endpoints de solo-lectura (panel browse, listados paginados) con CPU DB < 60% | Replica antes que upsize tier |
| Conexiones | > 80% del `max_connections` del tier Render | Replica + pooler (PgBouncer) |
| CPU primario | Saturado por SELECTs analíticos mientras writes son bajos | Offload reads |

**No** introducir replica si: transacciones largas en primario, mucho `VACUUM` pendiente, o lag de red > 50 ms RTT (peor UX que un primario más grande).

## Opciones de despliegue

### A) Render PostgreSQL (managed)

- Render soporta **read replicas** como add-on en planes elegibles (ver documentación actual de Render).
- **Pros:** mismo VPC-ish, backups coordinados, failover gestionado.
- **Contras:** coste fijo adicional; lag típico 100–800 ms bajo carga.

### B) Self-managed PostgreSQL (streaming replication)

- Primario en VM (Hetzner, AWS RDS no es self-managed pero similar).
- Réplica física con `wal_level = replica`, `max_wal_senders`, slot de replicación.
- **Pros:** control fino, réplicas múltiples, near-zero vendor lock.
- **Contras:** operación DBA (failover manual o Patroni).

## Cambios en aplicación (Flask / `get_api_db_cursor`)

1. **Dos DSN:** `DATABASE_URL` (primary) y `DATABASE_READ_REPLICA_URL` (opcional).
2. **Router de sesión:** decorador `@read_only` en rutas GET que no mutan estado.
3. **Consistencia:** usar réplica sólo cuando la ruta declare `staleness_ok=True`.
4. **ORM / cursor:** factoría `get_api_db_cursor(primary=True|False)`.

### Pseudocódigo (no implementado en este repo)

```python
def get_api_db_cursor(primary: bool = True):
    url = os.environ['DATABASE_URL'] if primary else os.environ.get('DATABASE_READ_REPLICA_URL')
    ...
```

## Clasificación de queries — tolerancia a lag

| Clase | Tolerancia lag | Ejemplos Argus | Routing |
| --- | --- | --- | --- |
| **L0 — fuerte consistencia** | **0 ms** (solo primary) | Login, issue plugin token, POST verdict, DELETE key, cualquier INSERT/UPDATE | Primary |
| **L1 — eventual < 500 ms** | Staff panel listados de scans recientes si el usuario acepta refresco | `GET /api/scans?page=` | Replica OK si banner "puede demorar 1s" |
| **L2 — eventual 1–5 s** | Dashboards agregados, heatmaps `plugin_violations`, rankings AI | `GET /api/admin/ai-health` | Replica preferida |
| **L3 — eventual > 5 s** | Export CSV masivo, analytics internos, `EXPLAIN` ad-hoc | Jobs batch | Réplica dedicada "analytics" |

### Tabla resumen

| Query / endpoint (conceptual) | Mínimo lag permitido | Réplica |
| --- | --- | --- |
| Autenticación / sesión | 0 | No |
| Crear scan token / plugin issue-token | 0 | No |
| Cerrar veredicto staff | 0 | No |
| Listar scans empresa (paginado) | 1 s | Sí (L1) |
| Oracle eval read-only (pesos + violations ya leídos) | 0 en misma request si escritura después | Mix: lecturas previas replica, persist primary |
| AI training cron | 5 s | Réplica analytics |
| Health `/api/health` COUNT(*) | 1 s | Sí (reduce carga) |

## Riesgos

- **Read-your-writes:** usuario crea token y redirige a lista; si la lista va a replica con lag, no ve el token → **frustración**. Mitigación: tras POST, forzar `primary=True` en la siguiente GET (cookie `last_write_ts`).
- **Replication lag monitoring:** alertar si `pg_stat_replication.replay_lag` > 2s (métrica en `monitoring-queries.sql`).

## Checklist previo a cutover

- [ ] Slot de replicación creado y lag estable < 500 ms.
- [ ] Variable `DATABASE_READ_REPLICA_URL` en Render.
- [ ] Tests de carga: 80% tráfico read a replica sin subir CPU primario.
- [ ] Rollback: quitar env var → todo vuelve a primary.
