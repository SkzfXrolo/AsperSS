# Argus Projects — DR drill plan (Pack 48-H Round 2)

## Objetivo

Validar mensualmente que **RTO real ≤ 4 h** y que los backups off-site son **restaurables** (no sólo que existen).

## Frecuencia

- **Drill completo:** 1× por mes (primer domingo 06:00 UTC sugerido).
- **Drill ligero (checksum only):** semanal si el equipo es pequeño.

## Roles

| Rol | Responsabilidad |
| --- | --- |
| **Driver** | Agenda ventana, ejecuta restore, documenta |
| **Witness** | Verifica conteos, smoke tests |
| **Owner** | Aprueba borrado de DB staging post-drill |

## Procedimiento (90–120 min)

### Fase A — Preparación (15 min)

1. Crear instancia PostgreSQL **staging** vacía (Render "new database" o local Docker PG14+).
2. Descargar el último backup cifrado `.dump.gpg` desde S3/B2.
3. `gpg --decrypt` → `.dump` custom.

### Fase B — Restore (30–90 min según tamaño)

```bash
pg_restore --clean --if-exists --no-owner --no-acl \
  --jobs=4 \
  --dbname="$STAGING_DATABASE_URL" \
  argus-latest.dump
```

- Si falla por extensión faltante: instalar mismas extensiones que prod (`CREATE EXTENSION IF NOT EXISTS`).

### Fase C — Integridad (20 min)

1. Ejecutar `scripts/db/integrity-checks.sql` contra staging.
2. Ejecutar `scripts/db/tenant-isolation-checks.sql`.
3. Ejecutar `scripts/db/data-quality.sql`.
4. Comparar **row counts** aproximados vs prod (query en `monitoring-queries.sql` sección table sizes).

**Aceptación:** cero violaciones HIGH en integrity; discrepancia de counts < 0.1% salvo tablas efímeras (`discord_queue`).

### Fase D — Smoke app (15 min)

1. Apuntar **sólo staging** con `DATABASE_URL` en un deploy preview de Render.
2. Login, listar scans, abrir un scan con resultados, panel plugin keys (read-only).
3. **No** ejecutar DELETE masivo en staging con datos reales anonimizados.

### Fase E — Post-mortem (15 min)

Documentar en ticket / Notion:

- Timestamp inicio/fin restore.
- Tamaño backup, velocidad MB/s.
- Errores `pg_restore` y cómo se resolvieron.
- RTO medido (T_restore_complete − T_start).

## Checklist post-restore (imprimible)

- [ ] `SELECT version();` coincide major PG con prod.
- [ ] Extensiones: `uuid-ossp`, etc.
- [ ] `pg_stat_user_tables` muestra tablas esperadas (≥40).
- [ ] `companies` tiene al menos la fila `arefy` si aplica.
- [ ] `users` admin existe.
- [ ] FK violations: `monitoring-queries.sql` bloque orphan check.
- [ ] App smoke: HTTP 200 en `/login`, `/api/health`.

## Rollback del drill

- Staging se puede **DROP DATABASE** al final.
- Prod no se tocó — sin rollback necesario.

## Hallazgos comunes en primer drill

- Extension `pgcrypto` no instalada en staging.
- Charset / collation distinta → índices text recreados OK pero orden distinto.
- Secuencias en tablas SERIAL desalineadas tras restore — ejecutar `setval` si la app inserta IDs fijos (raro).
