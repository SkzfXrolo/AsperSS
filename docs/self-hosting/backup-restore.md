# Backup y restore

## Backup PostgreSQL

`docker compose exec postgres pg_dump -U argus argus > backup.sql`

## Restore PostgreSQL

`cat backup.sql | docker compose exec -T postgres psql -U argus -d argus`

## Recomendaciones

- Backup diario con retencion 14/30 dias.
- Probar restore al menos una vez por mes.
