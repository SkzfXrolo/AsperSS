# Logical replication overview (Pack 48-H Round 5 · #134)

## Cuándo usar replicación lógica

La replicación **lógica** replica cambios a nivel de **filas** (DML) mediante el WAL decodificado. La replicación **física** (streaming) replica bytes de bloques al disco bit a bit.

| Criterio | Lógica | Física |
| --- | --- | --- |
| Major version distinta (origen vs destino) | Sí (con límites) | No (misma major) |
| Replicar subset de tablas | Sí | No (todo el cluster) |
| Zero-downtime upgrade | Patrón estándar | Requiere mismo major |
| DDL en primario | Se propaga según publicación | Sí (replica idéntica) |
| Latencia típica | Baja–media | Muy baja |
| Complejidad operativa | Alta | Media |

## Por qué lógica en Argus

1. **Upgrades PG** en Render o self-host sin ventana larga de downtime (ver `upgrade-zero-downtime.md`).
2. **CDC hacia DW/analytics** sin exponer todo el cluster (subset: `scans`, `ai_decisions_log`, etc.).
3. **Réplica de lectura** con tablas filtradas (ej. sólo datos anonimizados vía vistas + triggers — con precaución).

## Conceptos clave

- **Publisher** (primario): emite cambios.
- **Subscriber** (réplica lógica): aplica cambios.
- **Publication**: lista de tablas + opciones `INSERT/UPDATE/DELETE`.
- **Subscription**: conexión del subscriber al publisher + mapeo de tablas.
- **Replication slot**: retiene WAL hasta consumo; **riesgo de disco lleno** si el subscriber cae.

## Requisitos PostgreSQL

- PG 10+: publicaciones/suscripciones nativas.
- `wal_level = logical` en el publisher (Render: verificar tier; ver `render-limitations.md`).
- Tablas con **REPLICA IDENTITY** adecuado para `UPDATE/DELETE`:
  - `DEFAULT` (PK) suele bastar.
  - `FULL` si no hay PK (costoso en WAL).
  - `USING INDEX` si hay índice único alternativo.

## Limitaciones inherentes

- No replica **DDL** automáticamente al subscriber: hay que versionar schema en ambos lados o usar herramientas.
- **Sequences** no se replican como en física: requiere estrategia (sync manual, `serial` en subscriber independiente para writes).
- **Truncates** en PG <15 no replicaban bien; revisar versión.
- **Conflictos** si hay escritura en ambos lados (ver `conflict-resolution.md`).

## Cuándo NO usar lógica

- Réplica caliente **idéntica** para failover rápido sin divergencia → preferir streaming física + Patroni/repmgr.
- Carga OLTP con muchos `UPDATE` de filas anchas sin PK → WAL y CPU altos.

## Referencias cruzadas Pack 48

- `docs/db/zero-downtime-upgrade.md` (Round 3)
- `docs/db/cdc-design.md` (Round 3)
- `docs/db/render-runbook.md` (Round 4)
