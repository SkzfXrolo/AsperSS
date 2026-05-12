# Argus: cuándo sharding (Pack 48-H Round 6 · #153)

## Señales para considerar

- DB size > 500 GB y crecimiento sostenido.
- p95 queries panel no baja con índices + cache + replicas.
- CPU primary > 80% sostenido en horario business.
- IOPS techo del tier alcanzado y no upgradable.
- Multi-region con write-locality necesario.

## Antes de sharding (orden)

1. Indexar + cleanup retention.
2. PgBouncer + pool tuning.
3. Read replica + routing reads.
4. Partitioning RANGE en tablas grandes.
5. Vertical sharding por dominio.
6. **Sharding horizontal** (último recurso).

## Costos de sharding

- 3-5x complejidad ops.
- Migrations multi-shard.
- DR drills multiplicados.
- Cross-shard analytics requiere DW separado.

## Decisión Argus Pack 48

NO sharding. Roadmap re-evaluación: **Pack 60** o cuando se cruce un umbral arriba.

## Referencias

- `docs/db/sharding-design.md` (Round 2)
- `docs/db/cost-forecast.md`
