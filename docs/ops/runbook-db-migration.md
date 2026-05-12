# Runbook DB migrations zero-downtime

1. Aplicar migracion backward-compatible.
2. Desplegar app compatible con ambos esquemas.
3. Migrar datos en background.
4. Eliminar campos legacy en release posterior.
