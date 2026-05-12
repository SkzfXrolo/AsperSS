# Render PostgreSQL runbook (Pack 48-H Round 4 · #126)

## TL;DR

Render es nuestro proveedor PG actual. Este runbook compila las **limitaciones**, **acciones operativas** y **trade-offs** específicos de Render (vs PG self-host o RDS).

> Pricing/features Render se mueven. Fechas de validación al pie. **Verificar en Render dashboard** antes de cualquier acción crítica.

Última validación: snapshot 2026-Q2.

## Tiers (snapshot)

| Tier | RAM | CPU | Storage | Max connections | Backups retention | Read replicas | $/mes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Free | 256 MB | shared | 1 GB | 22 | 1 día | 0 | 0 |
| Basic | 1 GB | shared | 10 GB | 22 | 7 días | 0 | 7 |
| Standard | 4 GB | 2 vCPU | 60 GB | 97 | 7 días | hasta 1 | 35 |
| Pro | 16 GB | 4 vCPU | 200 GB | 197 | 30 días | hasta 2 | 95 |
| Pro+ | 32 GB | 8 vCPU | 500 GB | 397 | 30 días | hasta 5 | 195 |

(Verificar en Render console; tiers cambian de nombre.)

## Limitaciones conocidas (importan a Argus)

| Tema | Estado |
| --- | --- |
| `shared_preload_libraries` | **no editable** por usuario. `pg_stat_statements` viene por default en tiers pagos; otras (`pgaudit`, `pg_partman`, `pg_cron`) **NO** disponibles. |
| Extensions installables | subset oficial (ver `extensions-evaluation.md`). Render publica lista por versión. |
| `wal_level=logical` | habilitado en tiers Pro+ (necesario para logical replication / CDC). |
| `postgresql.conf` direct edit | NO. Cambios vía Render dashboard o `ALTER SYSTEM` limitado. |
| pg_repack | **no soportado** (requiere superuser). Workaround: ventana + `VACUUM FULL` o migrar fuera. |
| `pg_hba.conf` | gestionado por Render. Acceso via SSL forzado desde IPs allowlisted. |
| `LISTEN/NOTIFY` | sí, funciona. |
| Replication slot manual | sólo para replicas internas; CDC externo limitado. |
| Acceso al filesystem logs | NO. Logs via `render logs` o Datadog/etc integración. |
| Multi-region replica | en roadmap; hoy sólo intra-region. |
| Major version upgrade | Render hace in-place; ventana ~5-30 min. |

## Connection limits

Reglas operativas con Render PG:

| Workers gunicorn | Pool por worker | Total | Tier mínimo |
| --- | --- | --- | --- |
| 2 | 5 | 10 | Basic |
| 4 | 10 | 40 | Standard |
| 8 | 10 | 80 | Standard (tight) |
| 8 | 10 | 80 + replicas | Pro |

Con **PgBouncer** (sidecar en mismo service, ver `connection-pool.md` #91), multiplexamos cientos de clientes sobre <50 conexiones server.

## Backups

| Acción | Render | Recomendado complementar |
| --- | --- | --- |
| Backup automático diario | sí | sí, alineado con SLA |
| Point-in-time recovery (PITR) | tiers pagos | confirmar ventana |
| Restore a otro service | sí, vía dashboard | scripted con Render API |
| Backups offsite | **NO** | usar `backup-automation.sh` (#R2) + S3 |
| Encryption del backup | en reposo Render | GPG adicional para offsite |
| Test de restore | manual | drill mensual (`dr-drill-plan.md`) |

## Upgrade major version

Render ofrece in-place. Riesgo: 5-30min downtime.

Plan recomendado Argus:

| Approach | Cuándo |
| --- | --- |
| Render in-place | Pack 48 (today), si downtime aceptable |
| Logical replication (zero-downtime) | Pack 60+ si SLA exige <1min |

Ver `zero-downtime-upgrade.md` (#97).

## Monitoring options en Render

| Opción | Notas |
| --- | --- |
| Render dashboard | CPU/RAM/disk/connections básico |
| Render logs UI | tail vivo, búsqueda limitada |
| Datadog integration | logs + metrics, $$ |
| Better Stack / Logtail | logs |
| Self-host Grafana + `postgres_exporter` | requiere que Render permita conexión read; SSL OK |
| pganalyze (SaaS) | si pagamos, da queries top + recos |

Para Pack 48-50, recomendamos:

1. Render dashboard (gratis, métricas básicas).
2. Datadog free tier (logs + 1 dashboard).
3. Grafana self-host conectando con `monitor_ro` rol (`security-hardening.md`).

## Render-specific cost optimization

| Acción | Saving |
| --- | --- |
| Retention agresiva en logs/audit | reduce storage |
| Drop índices no usados | reduce storage + write amplification |
| Compresión a nivel app (jsonb gzip) en columnas históricas | medio |
| Replica off-hours | no posible en Render (always-on) |
| Archive a S3 Glacier para data >1 año | mejor ahorro |
| Backups offsite propios + bajar tier de retention Render | marginal |

Ver `cost-optimization.md` y `cost-forecast.md` (#107).

## Common operations

### Cambiar password de rol

```sql
ALTER ROLE app WITH PASSWORD '...';
```

Después: rotar `DATABASE_URL` en env de cada service. Render acepta env update sin reiniciar manualmente.

### Aplicar migration

1. PR aprobada → merge a main.
2. CI corre `alembic upgrade head` contra DB efímera, asserts pasan.
3. Deploy aplica migration **antes** de bootear nueva imagen app:
   ```bash
   alembic upgrade head && gunicorn ...
   ```
4. Si falla: rollback automático Render mantiene release anterior; aplicar `alembic downgrade -1` manualmente.

Ver `migration-runbook.md` y `migration-tooling-deep.md` (#127).

### Crear read replica

1. Dashboard → "Add replica".
2. Espera 5-15min sync.
3. Connect string visible.
4. App usa replica para reads: `DATABASE_URL_REPLICA`.

### Conectar localmente para debug

```bash
PGPASSWORD=$(render env get DATABASE_URL ...) \
  psql "$DATABASE_URL?sslmode=require"
```

Render PG tiene **external connection string** (vía Internet, autenticado) e **internal** (private network, sólo desde otros services Render). Preferir internal cuando sea posible.

### Pause / resume

Render no permite "pause" PG (cargo continúa).

## Incident escalation

| Severidad | Acción |
| --- | --- |
| DB inaccesible | Render status page + support ticket P0 |
| Performance degradación | revisar `pg_stat_activity`, dashboard Render |
| Backup falló | confirmar con dashboard, abrir ticket si crítico |
| Storage 90% | upgradar tier inmediato |

## Conocido / "REVIEW"

- **`pg_cron`**: solicitamos a Render; depende de tier y versión. Confirmar antes de planear MVs refresh con pg_cron (`materialized-views.md`).
- **`pg_partman`**: ídem.
- **`pgaudit`**: probablemente no; alternativa: `log_statement = 'mod'` y parsear logs.
- **`wal_level`**: confirmar `logical` antes de plan CDC.

## Anti-patterns en Render

1. ❌ Asumir `shared_preload_libraries` editable.
2. ❌ Confiar 100% en backups Render sin offsite.
3. ❌ Conectar Render PG via Internet sin `sslmode=require`.
4. ❌ Dejar tier free para producción real.
5. ❌ Olvidar que `pg_dump` necesita rol con `pg_read_server_files` o trabajar como owner.

## Referencias

- `connection-pool.md` (#91)
- `cost-optimization.md`
- `cost-forecast.md` (#107)
- `extensions-evaluation.md` (#96)
- `dr-drill-plan.md`
- `backup-strategy.md`
- `zero-downtime-upgrade.md` (#97)

## Notas de validación

Cada item marcado "snapshot 2026-Q2" debe re-verificarse en Render dashboard. Render publica changelogs. Mantener este doc actualizado cada major change.
