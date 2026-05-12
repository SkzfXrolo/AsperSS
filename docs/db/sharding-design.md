# Argus Projects — Sharding strategy (Pack 48-H Round 2)

## Cuándo shardar (umbrales)

| Métrica | Umbral | Notas |
| --- | --- | --- |
| Tamaño total DB | **> 100 GB** en disco con growth > 20%/año | Primero: archival S3 + partition |
| IOPS / throughput | Saturación sostenida pese a réplica y pooler | Shard horizontal |
| Single-table rows | **`scans` > 50M** o **`scan_results` > 200M** | Partición nativa antes que shard |
| Multi-tenant skew | Una `company_id` con >40% del total rows ("hot tenant") | Shard + rate limit + partition por company |

**Orden recomendado:** VACUUM full → partitioning por tiempo → read replicas → **último** sharding lógico.

## Shard keys candidatos

### 1) `company_id` (natural multi-tenant)

- **Pros:** aislamiento alineado con producto; cross-shard queries raras si casi todo filtra por empresa.
- **Contras:** hot shard si un mega-cliente domina; migración de staff global (superadmin) requiere federación.

### 2) `created_at` / partición temporal (range)

- **Pros:** archivado barato; queries típicas son recientes (`ORDER BY started_at DESC LIMIT`).
- **Contras:** no distribuye carga entre tenants; un mes puede estar caliente.

### 3) Híbrido (recomendado a largo plazo)

- Partición **primero** por `started_at` (mensual).
- Sub-partición o **routing** por `company_id` sólo si un tenant excede X GB/mes.

## Trade-offs

| Tema | Riesgo | Mitigación |
| --- | --- | --- |
| Hot shard | Un `company_id` satura un nodo | Shed load: rate limit API + move tenant a shard dedicado |
| Cross-shard JOIN | `scans` en shard A, `users` en shard B | Duplicar dimensión pequeña (`users`, `companies`) en cada shard o usar **Citus** reference tables |
| Rebalancing | Movimiento de rangos de keys costoso | Usar hash sharding con consistent hashing (cfr. Citus) |
| IDs globales | SERIAL local colisiona | UUID v7 o Snowflake IDs |

## Migration path (dual-write + backfill + cutover)

1. **Fase 0 — inventario:** tamaño por tabla, QPS por tenant, FK graph (ver `er-diagram.md`).
2. **Fase 1 — routing shadow:** app escribe solo primary; **lee** de nuevo shard en modo compare-only (diff log).
3. **Fase 2 — dual-write:** cada INSERT va a primary y a shard destino (idempotency keys).
4. **Fase 3 — backfill:** job nocturno copia histórico por rangos (`id BETWEEN` o `started_at`).
5. **Fase 4 — cutover reads:** feature flag `SHARD_READS=on` por porcentaje canario 1%→100%.
6. **Fase 5 — stop primary historical:** congelar writes viejos; primary pasa a archivo.
7. **Fase 6 — cleanup:** DROP partition antigua en primary tras validación legal.

**Rollback:** flag off + DNS/cursor a primary; nunca borrar primary hasta 30d post-cutover.

## Herramientas

- **Citus** (extension PG): sharding transparente para PG.
- **YugabyteDB** / **Cockroach**: si se abandona PG puro (alto costo migración).
- **No** shardar con micro-BDs por tenant salvo compliance extremo — operación explota.
