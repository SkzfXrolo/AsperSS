# Migracion desde Render a self-hosted

1. Exportar variables y secretos actuales.
2. Realizar backup de base de datos.
3. Levantar stack docker en entorno staging.
4. Restaurar DB y validar funcionalidades.
5. Cambiar DNS con ventana de mantenimiento corta.
6. Monitorear 24h y mantener rollback listo.
