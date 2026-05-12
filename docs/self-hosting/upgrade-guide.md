# Upgrade guide sin downtime

1. Preparar imagen nueva y deploy en nodo secundario.
2. Ejecutar migraciones backward-compatible.
3. Hacer switch gradual de trafico.
4. Verificar errores, latencia y healthchecks.
5. Retirar version anterior cuando la nueva este estable.
