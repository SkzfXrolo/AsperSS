# Argus Projects — Backup strategy (Pack 48-H Round 2)

## Objetivos

| Métrica | Target | Notas |
| --- | --- | --- |
| **RPO** (Recovery Point Objective) | **≤ 1 h** | Backups incrementales horarios + `pg_dump` custom diario si el volumen lo permite |
| **RTO** (Recovery Time Objective) | **≤ 4 h** | Incluye restore + smoke tests + DNS/cutover si nueva instancia |

Render managed PostgreSQL incluye backups automáticos; este documento cubre **defensa en profundidad** (copia off-site cifrada con script).

## Retención recomendada

| Tipo | Retención | Destino |
| --- | --- | --- |
| Diarios | **7 días** | S3 bucket `s3://argus-db-backups/daily/` |
| Semanales | **30 días** | `…/weekly/` |
| Mensuales | **365 días** | `…/monthly/` (Glacier opcional tras 90d) |

Rotación: lifecycle policy S3 para purgar automáticamente.

## Cifrado del backup

- **GPG** con clave pública del owner: el `.dump` custom se cifra antes de subir (`gpg --encrypt --recipient owner@domain`).
- La clave **privada** nunca en el servidor de backup; sólo la pública.

## Verificación

- **Checksum:** `sha256sum` archivo subido vs local antes de borrar temp.
- **Restore test:** ver `dr-drill-plan.md` mensual.

## Relación con Render

1. No desactivar backups nativos de Render.
2. El script `scripts/db/backup-automation.sh` es **adicional** (compliance / escape hatch).

## Riesgos

- Credenciales S3/B2 en env vars — rotar si leak.
- `pg_dump` largo puede competir IOPS: ejecutar en ventana valle.
