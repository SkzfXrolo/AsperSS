# Configuración de MySQL para Aspers Projects SS

Este documento explica cómo configurar MySQL para reemplazar SQLite y resolver el problema de persistencia de datos en Render.

## 🎯 ¿Por qué MySQL?

- **Persistencia real**: Los datos se mantienen después de reinicios del servidor
- **Escalabilidad**: Soporta múltiples conexiones concurrentes
- **Hosting gratuito**: Varias opciones gratuitas disponibles
- **Rendimiento**: Mejor que SQLite para aplicaciones web

## 🚀 Opciones de Hosting Gratuito

### 1. **PlanetScale** (Recomendado) ⭐
- **URL**: https://planetscale.com
- **Gratis**: 1 base de datos, 1GB almacenamiento, 1 billón de filas
- **Ventajas**: 
  - MySQL serverless nativo
  - SSL automático
  - Muy fácil de configurar
  - Sin límites de conexión

**Pasos**:
1. Crear cuenta en PlanetScale
2. Crear una base de datos
3. Obtener las credenciales de conexión
4. Configurar variables de entorno

### 2. **Railway**
- **URL**: https://railway.app
- **Gratis**: $5 crédito mensual (suficiente para MySQL)
- **Ventajas**: 
  - Muy fácil de usar
  - Integración con GitHub
  - Auto-deploy

### 3. **Render PostgreSQL** (Alternativa)
- **URL**: https://render.com
- **Gratis**: PostgreSQL gratuito
- **Nota**: Requiere cambios menores en el código (PostgreSQL en lugar de MySQL)

## 📋 Configuración en PlanetScale

### Paso 1: Crear Base de Datos

1. Ve a https://planetscale.com y crea una cuenta
2. Crea un nuevo proyecto
3. Crea una base de datos (ej: `aspers_ss_db`)
4. Ve a "Connect" y copia las credenciales

### Paso 2: Obtener Credenciales

PlanetScale te dará una cadena de conexión como:
```
mysql://[USER]:[PASSWORD]@[HOST]/[DATABASE]?sslaccept=strict
```

### Paso 3: Configurar Variables de Entorno en Render

En Render, agrega estas variables de entorno:

```bash
MYSQL_HOST=[HOST de PlanetScale]
MYSQL_PORT=3306
MYSQL_USER=[USER de PlanetScale]
MYSQL_PASSWORD=[PASSWORD de PlanetScale]
MYSQL_DATABASE=[DATABASE de PlanetScale]
```

**Ejemplo**:
```bash
MYSQL_HOST=aws.connect.psdb.cloud
MYSQL_PORT=3306
MYSQL_USER=abc123def456
MYSQL_PASSWORD=pscale_pw_xyz789
MYSQL_DATABASE=aspers_ss_db
```

### Paso 4: Inicializar Base de Datos

La base de datos se inicializará automáticamente cuando se ejecute la aplicación por primera vez.

O puedes ejecutar manualmente:
```bash
python -c "from db_mysql import init_mysql_db; init_mysql_db()"
```

## 📋 Configuración en Railway

### Paso 1: Crear Base de Datos MySQL

1. Ve a https://railway.app
2. Crea un nuevo proyecto
3. Agrega un servicio "MySQL"
4. Railway te dará las credenciales automáticamente

### Paso 2: Configurar Variables de Entorno

Railway expone las variables automáticamente, pero puedes configurarlas manualmente:

```bash
MYSQL_HOST=${{MySQL.MYSQLHOST}}
MYSQL_PORT=${{MySQL.MYSQLPORT}}
MYSQL_USER=${{MySQL.MYSQLUSER}}
MYSQL_PASSWORD=${{MySQL.MYSQLPASSWORD}}
MYSQL_DATABASE=${{MySQL.MYSQLDATABASE}}
```

## 🔄 Migración de Datos Existentes

Si ya tienes datos en SQLite, usa el script de migración:

```bash
# 1. Configurar variables de entorno MySQL
export MYSQL_HOST=...
export MYSQL_PORT=3306
export MYSQL_USER=...
export MYSQL_PASSWORD=...
export MYSQL_DATABASE=...

# 2. Ejecutar migración
python migrate_sqlite_to_mysql.py
```

El script:
- Busca `scanner_db.sqlite` en varias ubicaciones
- Conecta a MySQL
- Migra todas las tablas y datos
- Preserva relaciones y claves foráneas

## ✅ Verificación

Después de configurar MySQL, verifica que funciona:

```python
from db_mysql import get_db_connection, init_mysql_db

# Inicializar (solo la primera vez)
init_mysql_db()

# Probar conexión
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) as count FROM users")
result = cursor.fetchone()
print(f"Usuarios en BD: {result['count']}")
```

## 🔧 Solución de Problemas

### Error: "Access denied for user"
- Verifica que las credenciales sean correctas
- Asegúrate de que el usuario tenga permisos en la base de datos

### Error: "Can't connect to MySQL server"
- Verifica que el host y puerto sean correctos
- Asegúrate de que el firewall permita conexiones desde Render
- En PlanetScale, verifica que la base de datos esté activa

### Error: "SSL connection required"
- PlanetScale requiere SSL
- El código maneja SSL automáticamente
- Si usas otro host, configura `MYSQL_SSL_CA` si es necesario

### Datos no persisten
- Verifica que las variables de entorno estén configuradas correctamente
- Asegúrate de que `init_mysql_db()` se ejecute al iniciar
- Revisa los logs de Render para errores de conexión

## 📝 Notas Importantes

1. **Backup**: Aunque MySQL es persistente, siempre haz backups regulares
2. **Límites**: Revisa los límites de tu plan gratuito
3. **Seguridad**: Nunca commitees credenciales en Git
4. **Performance**: MySQL es más rápido que SQLite para múltiples conexiones

## 🎉 ¡Listo!

Una vez configurado, tus datos se mantendrán después de cada reinicio del servidor en Render.

