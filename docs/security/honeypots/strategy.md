# Honeypot & Canary Strategy

## Objetivo

Detectar acceso malicioso temprano con señuelos controlados.

## Ubicaciones sugeridas

- fila canary en DB con pseudo-admin fake (monitor de acceso),
- API keys falsas en documentación pública,
- archivo `.env` canary en entorno de honeynet,
- endpoints señuelo de baja interacción.

## Principios

- nunca mezclar canary con credencial real,
- todo hit debe generar alerta inmediata,
- rotación periódica de canaries.

## Riesgos

- falsos positivos por scanners automatizados,
- costos de triage si no hay correlación.
