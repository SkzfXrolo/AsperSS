# 🚀 Guía Rápida: Configurar MySQL/PostgreSQL Gratis (5 minutos)

## ⚠️ ACTUALIZACIÓN: PlanetScale ya no tiene plan gratuito

Si PlanetScale no tiene opción gratuita, usa una de estas alternativas:

## 🥇 OPCIÓN RECOMENDADA: Railway (MySQL Gratis)

**URL**: https://railway.app

### Paso 1: Crear cuenta en Railway (2 min)

1. Ve a https://railway.app
2. Haz clic en "Start a New Project" (puedes usar GitHub)
3. Confirma tu email

### Paso 2: Crear base de datos MySQL (1 min)

1. En Railway, haz clic en "New" → "Database" → "MySQL"
2. Railway crea la BD automáticamente
3. Las credenciales se generan automáticamente

### Paso 3: Obtener credenciales (1 min)

1. Haz clic en tu servicio MySQL
2. Ve a la pestaña "Variables"
3. Railway muestra todas las variables automáticamente:
   - **MYSQLHOST**: el host
   - **MYSQLPORT**: 3306
   - **MYSQLUSER**: el usuario
   - **MYSQLPASSWORD**: la contraseña
   - **MYSQLDATABASE**: el nombre de la BD

### Paso 4: Configurar en Render (1 min)

1. Ve a tu servicio en Render (el que tiene la web app)
2. Ve a "Environment"
3. Agrega estas variables:

Copia los valores de Railway y agrégalos en Render:

```
MYSQL_HOST=el_valor_de_MYSQLHOST_de_railway
MYSQL_PORT=3306
MYSQL_USER=el_valor_de_MYSQLUSER_de_railway
MYSQL_PASSWORD=el_valor_de_MYSQLPASSWORD_de_railway
MYSQL_DATABASE=el_valor_de_MYSQLDATABASE_de_railway
```

**Ejemplo real:**
```
MYSQL_HOST=containers-us-west-xxx.railway.app
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=abc123xyz789
MYSQL_DATABASE=railway
```

4. Haz clic en "Save Changes"

## Paso 5: Reiniciar servicio (30 seg)

1. En Render, ve a tu servicio
2. Haz clic en "Manual Deploy" → "Deploy latest commit"
3. O simplemente espera a que Render detecte los cambios y despliegue automáticamente

## ✅ ¡Listo!

Ahora:
- ✅ Los datos **persisten** después de cada deploy
- ✅ Los usuarios **no se pierden** al actualizar código
- ✅ Los tokens **se mantienen** entre reinicios
- ✅ Todo funciona **automáticamente**

## 🔍 Verificar que funciona

1. Crea un usuario desde el panel web
2. Haz un deploy (cambia algo en el código y sube a GitHub)
3. Verifica que el usuario sigue existiendo después del deploy

## 💡 Notas

- **Railway Free**: $5 crédito mensual (más que suficiente para MySQL)
- **Sin límites de conexión**: Puedes tener muchas conexiones simultáneas
- **SSL automático**: Seguro por defecto
- **Auto-deploy**: Se actualiza automáticamente

## 🔄 Alternativas si Railway no te funciona

Si Railway no está disponible, revisa `docs/ALTERNATIVAS_GRATIS_MYSQL.md` para otras opciones:
- **Render PostgreSQL** (gratis, ya lo tienes)
- **Supabase** (PostgreSQL gratis)
- **Neon** (PostgreSQL gratis)

## 🆘 Si algo falla

1. Verifica que las variables de entorno estén correctas
2. Revisa los logs de Render para ver errores de conexión
3. Asegúrate de que el servicio de MySQL en PlanetScale esté activo
4. El código tiene fallback a SQLite, así que no romperá nada si MySQL falla

## 📞 Soporte

Si tienes problemas, revisa:
- `docs/CONFIGURAR_MYSQL.md` - Documentación completa
- `docs/MIGRACION_MYSQL_PASOS.md` - Pasos detallados de migración

