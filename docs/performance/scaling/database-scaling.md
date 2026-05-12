# Database Scaling (Deep)

## Ruta de migracion recomendada

1. **Vertical scaling**: mas CPU/RAM/IOPS.
2. **Read replicas**: separar trafico de lectura.
3. **Particionado**: reducir working set y mejorar mantenimiento.
4. **Sharding**: dividir escritura por clave de negocio.

## Fase 1: Vertical

- Objetivo: ganar capacidad rapido sin cambios de app.
- Señales de salida: CPU > 70% sostenido, cache hit bajo, WAL saturado.

## Fase 2: Read replicas

- Enviar consultas de lectura no criticas a replicas.
- Mantener writes y lecturas de consistencia fuerte en primario.
- Añadir query routing por tipo de endpoint.

Ejemplo de parametros PostgreSQL (referencia inicial):

```ini
max_connections = 300
shared_buffers = 8GB
effective_cache_size = 24GB
wal_compression = on
max_wal_size = 8GB
hot_standby = on
max_standby_streaming_delay = 30s
```

## Fase 3: Particionado + sharding

- Particionar tablas de eventos por fecha/tenant.
- Elegir shard key estable (`tenant_id` o `user_id`).
- Implementar dual-write temporal y verificacion de consistencia.

## Riesgos y mitigaciones

- **Replica lag:** budgets de lag y fallback a primario.
- **Hot shards:** rebalancing por tenant y hash salting.
- **Complejidad operativa:** runbooks, observabilidad por shard y automatizacion.
