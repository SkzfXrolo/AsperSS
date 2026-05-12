# Logical replication on Render (Pack 48-H Round 5 · #134)

## Resumen

Render PostgreSQL es **managed**: no controlás `postgresql.conf` completo ni el filesystem del servidor. La replicación lógica **puede** estar disponible como publisher/subscriber **entre instancias** que vos administres como clientes, pero las capacidades dependen de:

- Tier del servicio (CPU, conexiones, features habilitadas).
- Versión de PostgreSQL ofrecida por Render.
- Políticas de red (internal URL vs external).

> **REVIEW obligatorio**: confirmar en dashboard/documentación Render actual si `wal_level=logical` está permitido en el tier de producción Argus.

## Publisher en Render

Checklist:

| Item | Notas |
| --- | --- |
| `wal_level` | Debe ser `logical` para publicaciones nativas. Si `replica`, no sirve como publisher lógico. |
| `max_replication_slots` | Límite bajo en tiers chicos; cada subscription consume 1 slot. |
| Conexiones entrantes | El subscriber conecta al host público o internal; firewall / IP allowlist. |
| SSL | Obligatorio `sslmode=require` mínimo. |

## Subscriber en Render

- Segunda instancia Render como subscriber: viable si networking y permisos lo permiten.
- Subscriber **fuera** de Render (RDS, self-host): patrón común para DW/CDC.

## Riesgos específicos managed

1. **Upgrade in-place** de Render puede resetear/reconfigurar parámetros: re-validar `wal_level` post-upgrade.
2. **Disk WAL** y slots: si Render no expone métricas finas, instrumentar vía queries (`pg_replication_slots`, `pg_size_pretty(pg_wal_lsn_diff(...))`).
3. **No superuser**: operaciones como crear ciertos objetos o ajustar parámetros globales pueden estar bloqueadas.

## Patrones viables Argus

| Patrón | Viabilidad |
| --- | --- |
| Render PG (pub) → self-host analytics PG (sub) | Alta si networking OK |
| Render PG → Render PG (HA lógica) | **REVIEW** con documentación actual |
| Logical rep solo para major upgrade | Depende de poder levantar 2da instancia temporal |

## Alternativas si logical rep no está disponible

- `pg_dump` / `pg_restore` con ventana (`migration-runbook.md`).
- ETL incremental por timestamps (`dw-export-design.md`).
- Debezium desde RDS migrado fuera de Render (si se cambia hosting).

## Referencias

- `docs/db/render-runbook.md`
- `docs/db/zero-downtime-upgrade.md`
