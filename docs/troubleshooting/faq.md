# FAQ y troubleshooting

## Error: servicio web no levanta
- Revisar `docker compose logs web`.
- Confirmar variables en `docker/.env`.

## Error: DB no conecta
- Validar `DATABASE_URL`.
- Verificar health de `postgres`.

## Error: plugin no carga
- Confirmar Java y versión de server.
- Revisar logs de arranque del plugin.
