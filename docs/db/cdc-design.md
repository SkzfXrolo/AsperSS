# Argus Projects — CDC (Change Data Capture) design (Pack 48-H Round 3 · #92)

## ¿Por qué CDC?

Hoy todos los consumidores de eventos (cache invalidation, push WebSocket al panel, futuros sinks DW/search) hacen **polling** o reciben **callbacks ad-hoc** desde código de aplicación. Problemas:

1. **Acoplamiento**: cada nuevo consumer requiere editar `app.py`.
2. **Pérdida**: si la app crashea entre `INSERT` y `notify`, el consumer pierde el evento.
3. **Latencia variable**: pollers de 30s no funcionan para dashboards en vivo.

**CDC** lee directamente del **WAL** de Postgres y emite un evento por cada `INSERT/UPDATE/DELETE`, con garantía at-least-once.

## Use cases concretos en Argus

| Caso | Tabla origen | Consumer | Acción |
| --- | --- | --- | --- |
| Invalidar cache de dashboard | `scans` | Redis | DEL `dash:<company_id>:overview` |
| Push WebSocket al staff panel | `plugin_violations` | Pusher / Socket.IO | Emit `violation` event |
| Sync con DW | `scans`, `ai_decisions_log`, `violations` | BigQuery / DuckDB | Append a tabla raw |
| Search index | `ai_player_profiles` | Meilisearch / OpenSearch | Reindex doc |
| Audit pipeline | `staff_audit_log` | SIEM | Forward syslog/JSON |
| Anti-fraude | `companies`, `users` | Worker async | Eval risk score |

## Opciones técnicas

### A) `LISTEN/NOTIFY` (built-in, sin extra infra)

Triggers en cada tabla → `NOTIFY argus_changes, json_payload`. La app web (u otro listener) hace `LISTEN argus_changes`.

| Pros | Cons |
| --- | --- |
| Cero infra extra | Sin persistencia (mensaje perdido si listener desconectado) |
| Latencia <100ms | Payload limitado 8KB |
| Funciona en Render PG | No escala >1k events/s |

**Veredicto**: bueno para cache invalidation **rápida**, no para auditoría confiable.

### B) **Logical replication** (PG10+, built-in)

`CREATE PUBLICATION` + `CREATE SUBSCRIPTION` o consumir slot con cliente externo (e.g. `wal2json` + parser propio).

| Pros | Cons |
| --- | --- |
| Garantías de orden por tabla | Requiere `wal_level=logical` (Render lo permite) |
| Replicación selectiva por tabla | Consumer debe ack offsets |
| At-least-once | Slot inactivo retiene WAL → riesgo disk full |

**Veredicto**: opción **recomendada** para downstream "fiable" (DW, audit SIEM).

### C) Debezium (Kafka Connect)

Worker Java que lee slot de PG y publica a Kafka. Schema registry, transformaciones.

| Pros | Cons |
| --- | --- |
| Industry standard | Infra completa Kafka + ZooKeeper/KRaft + Connect |
| Schemas evolucionables | $$$ y operativa pesada |
| Conectores listos para múltiples sinks | Overkill para Argus actual |

**Veredicto**: válido si **multi-team** lo justifica. Hoy no.

### D) AWS DMS / Render addons

Outsourceado. Cobertura más alta de fuentes/sinks, pero lock-in y costo.

**Veredicto**: revisar si llegamos a >10TB DB.

## Recomendación

**Híbrido inicial**:

1. **NOTIFY** para invalidaciones rápidas (cache, WS push) — fire-and-forget aceptable.
2. **Logical replication slot + worker Python** consumiendo `wal2json` para sinks fiables (DW, SIEM).

Migrar a Debezium **sólo si**: aparecen >3 downstream teams, o se necesita schema registry compartido.

## Esquema del change event (formato propio)

```json
{
  "ts":         "2026-05-12T08:42:11.122Z",
  "op":         "I",                 // I=insert, U=update, D=delete
  "schema":     "public",
  "table":      "scans",
  "lsn":        "1A/3E0F2B8",
  "txid":       82734,
  "company_id": 14,                  // tenant key (si la tabla lo tiene)
  "before":     null,                // null para insert
  "after": {
    "id": 99812,
    "started_at": "2026-05-12T08:42:10Z",
    "verdict": "ban",
    "risk_score": 87
  }
}
```

## Pipeline propuesto

```
PG WAL
  ├─► slot wal2json ──► python worker (asyncio)
  │                       ├─► Redis Streams "argus.cdc.scans"
  │                       ├─► S3/Parquet (batched, hourly)
  │                       └─► SIEM (https POST)
  └─► trigger NOTIFY ──► web workers (LISTEN)
                          └─► cache invalidate / WS broadcast
```

## Tablas dentro de CDC vs. fuera

| Categoría | Tablas | CDC? |
| --- | --- | --- |
| **Transactional core** | scans, scan_results, ai_decisions_log, plugin_violations | ✅ |
| **Tenant config** | companies, users, plugin_keys | ✅ (low volume) |
| **Cache/tmp** | scan_tokens, rate_limit_buckets | ❌ ruido |
| **Auditoría** | staff_audit_log | ✅ (forward a SIEM) |
| **MV / derived** | mv_*, dw_* | ❌ |

## Riesgos & mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Slot inactivo retiene WAL ilimitado | Monitor `pg_replication_slots.active` + alerta + auto-drop slot >24h inactivo. |
| Reprocessing tras crash | Idempotencia: sinks deduplican por `(lsn, table, pk)`. |
| PII en eventos | Aplicar anonimización en el worker (hash, drop columns) antes de salir del perímetro. |
| Schema change rompe consumers | Versionar event payload con `_schema_v`; comunicar deprecación. |
| Latencia inaceptable | Worker debe correr en mismo VPC/region que PG; medir lag con `SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) FROM pg_replication_slots`. |

## Roadmap

| Fase | Entregable | Effort |
| --- | --- | --- |
| 0 | Probar `wal_level=logical` en staging Render | 2h |
| 1 | NOTIFY triggers en `scans`, `plugin_violations` | 4h |
| 2 | Worker Python lee slot, escribe Redis Streams | 1d |
| 3 | Sink S3 Parquet hourly | 1d |
| 4 | SIEM sink (audit_log) | 0.5d |
| 5 | Eval Debezium si crece consumer count | TBD |

## Cómo monitorear

```sql
-- slot lag (bytes)
SELECT slot_name, active, restart_lsn,
       pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS bytes_behind
FROM pg_replication_slots;

-- subscription lag (si se usa SUBSCRIPTION nativa)
SELECT subname, latest_end_lsn, latest_end_time,
       (NOW() - latest_end_time)                AS time_lag
FROM pg_stat_subscription;
```

## Referencias internas

- `docs/db/dw-export-design.md` — sink Parquet detallado.
- `docs/db/etl-pipeline-design.md` — staging post-CDC.
- `docs/db/edge-cases-playbook.md` — qué hacer si slot lagged.
