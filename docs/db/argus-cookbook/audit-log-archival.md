# Audit log archival (Pack 48-H Round 6 · #163)

## Estado

`staff_audit_log` crece moderado; legal puede exigir años.

## Estrategia

1. Particionar trimestralmente.
2. DETACH partition > N años aprobados.
3. Dump GPG-encrypted a S3 Glacier.
4. Mantener manifest `archived_partitions(partition, period, s3_url, sha256)`.

## Verificación

- `data-quality-framework/dq-checks-catalog.md` DQ-005-style FK integrity.
- Restore drill anual: pull from S3 + restore.

## Referencias

- `docs/db/backup-advanced/cross-region-backup.md`
- `docs/db/partitioning-deep/argus-partitioning-candidates.md`
