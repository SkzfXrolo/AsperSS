# DB cost forecast (Pack 48-H Round 3 · #107)

## Modelo

```
cost_total = cost_compute + cost_storage + cost_iops + cost_backups + cost_replicas + cost_egress
```

Cada componente: ver tabla. Costos basados en pricing Render PG **2026-Q2** y AWS S3 us-east. Ajustar al momento real.

## Pricing snapshot

| Tier Render PG | RAM | CPU | Storage incluido | $/mes (snapshot 2026-Q2) |
| --- | --- | --- | --- | --- |
| Free | 256 MB | shared | 1 GB | 0 |
| Basic | 1 GB | shared | 10 GB | 7 |
| Standard | 4 GB | 2 vCPU | 60 GB | 35 |
| Pro | 16 GB | 4 vCPU | 200 GB | 95 |
| Pro+ | 32 GB | 8 vCPU | 500 GB | 195 |
| Heroku-large | 64 GB | 16 vCPU | 1 TB | 395 |

Storage extra: ~$0.20/GB/mes.
IOPS: incluidos en tier (Render no factura per-IOP).
Backup automático: incluido.
Read replica: ~precio igual al primario.
Egress: $0.10/GB después de free tier.

## Estado actual (estimado Pack 48)

| Dimensión | Valor estimado | Razón |
| --- | --- | --- |
| DB size | 1-3 GB | Estimado de cantidad de scans + violations + matriz |
| Tier actual | Basic o Standard | Asumir Standard ($35) |
| Read replicas | 0 | — |
| Backups | Render included | — |
| Egress | <1 GB/mes | bajo tráfico hoy |
| **Costo mensual estimado** | **$35** | |

## Drivers de crecimiento

Tabla aproximada de growth rate, **por cliente activo** (jugadores escaneando):

| Tabla | Filas/mes/cliente | Bytes/fila aprox | GB/mes/cliente |
| --- | --- | --- | --- |
| scans | 30 000 | 250 | 0.0075 |
| scan_results | 30 000 | 500 | 0.015 |
| plugin_violations | 60 000 | 200 | 0.012 |
| ai_decisions_log | 30 000 | 300 | 0.009 |
| staff_audit_log | 1 000 | 200 | 0.0002 |
| ai_player_profiles | <100 | 1 000 | 0.0001 |
| logs/audit | 5 000 | 500 | 0.0025 |
| **Total** | | | **~0.046 GB/mes/cliente** |

Con índices + bloat: **~0.07 GB/mes/cliente**.

## Proyección 12 meses

Asumiendo crecimiento de clientes 10/mes (conservador), 25/mes (objetivo), 60/mes (optimista):

| Mes | Conservador | Objetivo | Optimista |
| --- | --- | --- | --- |
| t (hoy) | 10 clientes / 5 GB | 10 / 5 | 10 / 5 |
| t+3 | 40 / 8 | 85 / 11 | 190 / 18 |
| t+6 | 70 / 10 | 160 / 19 | 370 / 31 |
| t+9 | 100 / 12 | 235 / 26 | 550 / 44 |
| t+12 | 130 / 14 | 310 / 33 | 730 / 58 |

(Storage en GB incluye bloat 30% y growth de tablas no-lineales.)

## Cuándo cambiar tier

| Trigger | Acción |
| --- | --- |
| DB > 50 GB | upgrade Standard → Pro ($95) |
| DB > 150 GB | upgrade Pro → Pro+ ($195) |
| p95 dashboard > 1.5s | upgrade o read replica |
| CPU sostenido > 70% | upgrade tier o partitioning |
| Connections > 80% del cap | introducir PgBouncer (no cuesta extra) |

## Opciones de reducción de costo

1. **Retención agresiva** (`cleanup-policy-pack48.sql`) — recortar 30-50% del storage de logs.
2. **Partitioning** + drop de particiones viejas (#89) — barato.
3. **Compresión TimescaleDB** (#94) — 10× pero requiere self-host.
4. **Archive a S3 Glacier** ($0.004/GB/mes) — para data >1 año, casi gratis.
5. **Read replica sólo en hora pico** (no soportado por Render directo).
6. **Eliminar índices no usados** (`monitoring-queries.sql` top index) — libera storage + reduce write amplification.

## Ahorros estimados (escenario "Objetivo" mes 12, 33 GB)

| Acción | Saving / mes |
| --- | --- |
| Retention -30% | $7 (storage) |
| Drop unused indexes | $3 |
| Archive a S3 Glacier (10 GB) | $1.5 |
| **Total** | **~$11/mes** sobre $95 |

## Cuándo migrar fuera de Render

| Escenario | Trigger | Destino |
| --- | --- | --- |
| Storage > 1 TB | $395+/mes | self-host PG en VM dedicada |
| Lock-in feature falta | Render no soporta TimescaleDB | self-host o Aiven/Crunchy |
| Multi-region | clientes EU lo piden | AWS RDS multi-AZ / Aurora |
| Compliance SOC2/HIPAA | clientes enterprise | Provider con cert (Crunchy) |

## Implementación

- Mensual: ejecutar `scripts/db/cost-projection.py --current-clients N --current-gb G` para generar tabla.
- Compartir con Founder.
- Actualizar pricing si Render cambia tarifas.

## Riesgos del modelo

- Pricing Render puede cambiar.
- Crecimiento real lineal ≠ exponencial; ajustar trimestralmente.
- Costo de bandwidth (egress) puede saltar si activamos CDC out-of-region.
- Multi-region duplica casi todo.
