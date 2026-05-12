# Service Health Checks (Pack48-G)

## Tipos

- Liveness: proceso vivo.
- Readiness: listo para recibir tráfico.
- Startup: inicialización completa.

## Endpoints sugeridos

- `/health/live`
- `/health/ready`
- `/health/startup`

## Qué verificar

- DB conectividad
- Redis conectividad
- Dependencias externas críticas
- espacio de disco/memoria

## Degradación inteligente

- No tumbar readiness por dependencia no crítica.
- Exponer estado parcial y fallback activo.
