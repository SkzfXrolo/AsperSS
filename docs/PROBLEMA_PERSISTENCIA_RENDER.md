# ⚠️ Problema de Persistencia de Datos en Render

## 📋 Descripción del Problema

Cuando el servidor se reinicia en Render (por ejemplo, después de compilar una nueva versión), **los datos almacenados en SQLite se pierden**. Esto incluye:

- ✅ Tokens de escaneo (`scan_tokens`)
- ✅ Escaneos realizados (`scans`)
- ✅ Resultados de escaneos (`scan_results`)
- ✅ Historial de bans (`ban_history`)
- ✅ Feedback del staff (`staff_feedback`)
- ✅ Patrones aprendidos (`learned_patterns`)
- ✅ Hashes aprendidos (`learned_hashes`)

## 🔍 Causa Raíz

Render usa un **sistema de archivos efímero** para servicios gratuitos. Esto significa que:

1. Cuando el servicio se reinicia, el sistema de archivos se resetea
2. Los archivos SQLite (`scanner_db.sqlite`) se eliminan
3. La base de datos se recrea vacía al iniciar

## ✅ Soluciones

### Opción 1: PostgreSQL (Recomendado para Producción)

**Ventajas:**
- ✅ Persistencia garantizada
- ✅ Escalable
- ✅ Soporta múltiples servicios conectándose simultáneamente
- ✅ Backup automático

**Pasos:**

1. **Crear base de datos PostgreSQL en Render:**
   - Ve a Render Dashboard
   - Click **"New +"** → **"PostgreSQL"**
   - Configura nombre y región
   - Click **"Create Database"**

2. **Obtener la URL de conexión:**
   - Copia la **"Internal Database URL"** o **"External Database URL"**
   - Ejemplo: `postgresql://user:pass@host:5432/dbname`

3. **Actualizar código para usar PostgreSQL:**
   - Instalar dependencia: `pip install psycopg2-binary`
   - Modificar `source/api_server.py` para usar PostgreSQL en lugar de SQLite
   - Configurar variable de entorno `DATABASE_URL` en Render

### Opción 2: Volumen Persistente (Solo Planes de Pago)

**Ventajas:**
- ✅ Mantiene SQLite sin cambios de código
- ✅ Persistencia garantizada

**Desventajas:**
- ❌ Requiere plan de pago en Render
- ❌ Más costoso

### Opción 3: Backup Automático a S3/GCS (Solución Temporal)

**Ventajas:**
- ✅ Funciona con plan gratuito
- ✅ Backup automático de la BD

**Desventajas:**
- ❌ Requiere código adicional para backup/restore
- ❌ Puede haber pérdida de datos entre backups

**Implementación:**

1. Configurar S3 o Google Cloud Storage
2. Crear script que haga backup periódico de `scanner_db.sqlite`
3. Restaurar automáticamente al iniciar el servicio

### Opción 4: Migración Manual (Solución Temporal)

**Pasos:**

1. Antes de reiniciar, exportar datos:
   ```bash
   python migrate_local_data.py --export --output backup.sqlite
   ```

2. Después de reiniciar, importar datos:
   ```bash
   python migrate_local_data.py --import --input backup.sqlite
   ```

## 🚨 Nota Importante

**Los datos de autenticación (`users`, `companies`, `registration_tokens`) NO se pierden** porque están en una base de datos separada (`auth.db`) que se inicializa correctamente en cada inicio.

## 📝 Recomendación

Para producción, **usar PostgreSQL** es la mejor opción. Para desarrollo/testing, puedes usar la migración manual o aceptar que los datos se pierdan en cada reinicio.

