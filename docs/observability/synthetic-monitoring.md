# Synthetic Monitoring (Pack48-G)

## Objetivo

Detectar caídas/regresiones antes de que afecten masivamente a usuarios.

## Herramientas sugeridas

- Datadog Synthetics
- Pingdom
- UptimeRobot
- Checkly

## Flujos a monitorear

1. Login flow
2. Submit scan flow
3. Oracle eval flow
4. Panel browse flow

## Cadencia

- Uptime básico: cada 1 minuto
- Flujos completos: cada 10-15 minutos

## Geo distribución

- Al menos US / EU / SA para visibilidad de latencia regional.

## Alertas

- Falla consecutiva x3 -> alerta sev alta.
- Degradación de latencia > 30% sostenida -> alerta media.
