# Argus current vs projected (Pack 48-H Round 6 · #161)

## Tabla resumen (orientativa)

| Métrica | Hoy (est.) | 6m | 12m | 24m |
| --- | --- | --- | --- | --- |
| DB size | X GB | 1.5X | 2.5X | 4X |
| Active companies | C | 1.5C | 2.5C | 4C |
| Scans/día | S | 1.5S | 2.5S | 4S |
| Connections peak | P | 1.3P | 1.8P | 2.5P |

(Reemplazar con números reales `cost-projection.py`.)

## Decisiones disparadas

- Tier Standard → Pro cuando DB > 50 GB sostenido.
- Read replica cuando p95 panel > 250 ms 7d.
- Partitioning cuando `scans` > 50M filas o 50 GB.

## Owner

DBA + Owner producto deciden upgrades; H mantiene proyección.

## Referencias

- `docs/db/cost-forecast.md`
