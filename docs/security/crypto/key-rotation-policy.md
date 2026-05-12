# Crypto Key Rotation Policy

## Periodicidad

- API keys: 90 días
- Session secrets: 30 días
- DB encryption keys: 365 días
- Plugin/scanner shared secrets: 180 días

## Runbook general

1. generar nueva clave,
2. desplegar en modo dual-key (old+new),
3. rotar consumidores,
4. revocar old key,
5. verificar métricas y cerrar cambio.

## Controles

- inventario central de claves,
- expiración obligatoria,
- alertas pre-expiry.
