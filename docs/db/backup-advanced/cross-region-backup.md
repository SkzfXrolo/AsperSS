# Cross-region backup (Pack 48-H Round 5 · #145)

## Por qué

Desastre regional (AWS us-east-1 incident style) puede borrar primary **y** backups si están mismo bucket/region sin replicación.

## Estrategias

| Estrategia | Descripción |
| --- | --- |
| Cross-region replication S3 | bucket replication RR |
| Copy job async | cron copia a bucket secundario |
| Air-gapped | tape/out-of-cloud mensual compliance |

## Cifrado

- GPG como en `backup-automation.sh`.
- KMS keys distintas por región (rotación).

## Argus

Objetivo Pack 50: backups cifrados en **>=2 regiones** proveedor cloud.

## Referencias

- `docs/db/backup-strategy.md`
- `docs/db/security-advanced/network-security.md`
