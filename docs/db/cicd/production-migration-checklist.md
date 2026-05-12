# Production migration checklist (Pack 48-H Round 6 · #164)

## Pre-deploy

- [ ] PR aprobada por DBA.
- [ ] CI checks pasaron (`migration-ci-checks.md`).
- [ ] Ventana coordinada / off-peak.
- [ ] Backup fresco verificado.
- [ ] Plan rollback documentado.
- [ ] Monitoreo activo (`dashboards.md`).
- [ ] On-call notificado.

## Deploy

- [ ] `alembic upgrade head` exitoso.
- [ ] Smoke queries panel + Oracle OK.
- [ ] Locks dentro de límite.
- [ ] Replication lag stable.

## Post-deploy

- [ ] `ANALYZE` tablas tocadas.
- [ ] Verificar `pg_stat_statements` no muestra regresión.
- [ ] Dejar 30 min watch.
- [ ] Documentar en changelog.

## Referencias

- `docs/db/migration-runbook.md`
- `docs/db/on-call-playbook.md`
