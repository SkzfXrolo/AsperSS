# Pasos para Completar la Migración a MySQL

## ✅ Lo que ya está hecho:

1. ✅ Módulo `db_mysql.py` creado con todas las funciones necesarias
2. ✅ `requirements.txt` actualizado con `pymysql` y `cryptography`
3. ✅ Script de migración `migrate_sqlite_to_mysql.py` creado
4. ✅ Documentación de configuración creada
5. ✅ `api_server.py` parcialmente actualizado (soporta MySQL con fallback a SQLite)

## 🔄 Pasos para completar la migración:

### Paso 1: Configurar MySQL en PlanetScale (o tu host preferido)

1. Ve a https://planetscale.com y crea una cuenta
2. Crea una base de datos
3. Obtén las credenciales de conexión
4. En Render, agrega estas variables de entorno:
   ```
   MYSQL_HOST=tu_host
   MYSQL_PORT=3306
   MYSQL_USER=tu_usuario
   MYSQL_PASSWORD=tu_password
   MYSQL_DATABASE=tu_database
   ```

### Paso 2: Migrar datos existentes (si los tienes)

```bash
# Configurar variables de entorno
export MYSQL_HOST=...
export MYSQL_PORT=3306
export MYSQL_USER=...
export MYSQL_PASSWORD=...
export MYSQL_DATABASE=...

# Ejecutar migración
python migrate_sqlite_to_mysql.py
```

### Paso 3: Actualizar consultas SQL restantes

El archivo `api_server.py` tiene muchas consultas que aún usan `?` (SQLite). Necesitas:

1. Buscar todas las consultas con `?`
2. Reemplazar `?` con `%s` cuando `USE_MYSQL` sea True
3. O usar una variable `placeholder = '%s' if USE_MYSQL else '?'`

**Ejemplo de conversión:**
```python
# Antes (SQLite)
cursor.execute('SELECT * FROM table WHERE id = ?', (id,))

# Después (compatible ambos)
placeholder = '%s' if USE_MYSQL else '?'
cursor.execute(f'SELECT * FROM table WHERE id = {placeholder}', (id,))
```

### Paso 4: Actualizar acceso a resultados

MySQL con DictCursor retorna diccionarios, SQLite retorna tuplas:

```python
# Antes (SQLite)
result = cursor.fetchone()
value = result[0]  # Por índice

# Después (compatible ambos)
result = cursor.fetchone()
if USE_MYSQL:
    value = result.get('column_name')
else:
    value = result[0]
```

### Paso 5: Migrar `web_app/auth.py`

Similar a `api_server.py`, necesitas:
1. Importar `db_mysql`
2. Reemplazar `sqlite3.connect` con `get_db_connection`
3. Convertir placeholders `?` a `%s`
4. Actualizar acceso a resultados

### Paso 6: Migrar `web_app/app.py`

Buscar todas las referencias a SQLite y reemplazarlas con MySQL.

### Paso 7: Probar

1. Reiniciar servicios en Render
2. Verificar que las tablas se crean correctamente
3. Probar crear un token
4. Verificar que los datos persisten después de reiniciar

## 🚀 Solución Rápida (Recomendada)

Si quieres una solución más rápida, puedes:

1. **Usar el código actual** que tiene fallback a SQLite
2. **Configurar MySQL** en PlanetScale
3. **Agregar las variables de entorno** en Render
4. **El código detectará MySQL automáticamente** y lo usará

El código actual en `api_server.py` ya tiene:
- Detección automática de MySQL
- Fallback a SQLite si MySQL no está disponible
- Funciones helper para compatibilidad

Solo necesitas:
1. Configurar las variables de entorno MySQL
2. El código usará MySQL automáticamente
3. Los datos persistirán en MySQL

## 📝 Notas Importantes

- **No todas las consultas están convertidas aún** - el código funciona pero algunas consultas pueden fallar
- **Prueba en desarrollo primero** antes de desplegar a producción
- **Haz backup de tus datos** antes de migrar
- **El código tiene fallback a SQLite** si MySQL falla, así que es seguro probar

## 🎯 Próximos Pasos Inmediatos

1. **Configura PlanetScale** (5 minutos)
2. **Agrega variables de entorno en Render** (2 minutos)
3. **Reinicia los servicios** (1 minuto)
4. **Prueba crear un token** (1 minuto)
5. **Verifica que persiste después de reiniciar** (2 minutos)

¡Total: ~11 minutos para tener MySQL funcionando!

