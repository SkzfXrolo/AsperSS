# Partition maintenance (Pack 48-H Round 6 · #152)

## Tareas periódicas

| Tarea | Frecuencia |
| --- | --- |
| Crear partition futura | mensual / semanal según granularidad |
| DETACH + DROP / archive partition antigua | post retention legal |
| ANALYZE partition | tras carga masiva |
| REINDEX CONCURRENTLY índices locales | ventana |
| Verificar `default` partition no acumule | weekly |

## Automatización

| Opción | Notas |
| --- | --- |
| `pg_partman` | extensión dedicada; **REVIEW** Render |
| Cron app + función PL/pgSQL | manual pero portable |
| Job DBA | bash + psql |

## Default partition

```sql
CREATE TABLE scans_default PARTITION OF scans DEFAULT;
```

- Si recibe rows → bug en config (faltan particiones futuras).
- Alertar si rowcount > 0.

## DETACH vs DROP

- `DETACH CONCURRENTLY` (PG14+): saca partition sin lock fuerte.
- `DROP TABLE` luego de archivar a S3 si compliance lo permite.

## Argus runbook (resumen)

1. Job semanal crea partition `scans_YYYY_MM` siguiente.
2. Job mensual DETACH partition oldest > retención + dump a S3.
3. Monitoreo: alerta si próxima partition no existe a T-7d del rollover.

## Referencias

- `scripts/db/partition-migration.sql`
- `docs/db/argus-cookbook/audit-log-archival.md`
