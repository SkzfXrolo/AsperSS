# 🆓 Alternativas Gratuitas a PlanetScale para MySQL/PostgreSQL

Si PlanetScale no tiene plan gratuito disponible, aquí tienes **alternativas 100% gratuitas**:

## 🥇 Opción 1: Railway (Recomendado) ⭐

**URL**: https://railway.app

### Ventajas:
- ✅ **$5 crédito mensual GRATIS** (suficiente para MySQL)
- ✅ MySQL y PostgreSQL disponibles
- ✅ Muy fácil de configurar
- ✅ Integración con GitHub
- ✅ Auto-deploy automático

### Pasos:

1. **Crear cuenta**: https://railway.app (con GitHub)
2. **Crear proyecto nuevo**
3. **Agregar servicio** → "Database" → "MySQL"
4. **Railway te da las credenciales automáticamente**
5. **En Render, agrega estas variables** (Railway las expone automáticamente):
   ```
   MYSQL_HOST=${{MySQL.MYSQLHOST}}
   MYSQL_PORT=${{MySQL.MYSQLPORT}}
   MYSQL_USER=${{MySQL.MYSQLUSER}}
   MYSQL_PASSWORD=${{MySQL.MYSQLPASSWORD}}
   MYSQL_DATABASE=${{MySQL.MYSQLDATABASE}}
   ```

**Nota**: Si Railway y Render están en proyectos diferentes, copia las credenciales manualmente desde Railway.

---

## 🥈 Opción 2: Render PostgreSQL (Gratis) ⭐

**URL**: Ya lo tienes (Render)

### Ventajas:
- ✅ **100% GRATIS** (PostgreSQL gratuito)
- ✅ Ya estás usando Render
- ✅ Mismo dashboard
- ✅ Muy fácil de agregar

### Pasos:

1. En Render, ve a tu dashboard
2. Haz clic en "New +" → "PostgreSQL"
3. Nombre: `aspers_ss_db`
4. Plan: **Free**
5. Región: La misma que tu web app
6. Haz clic en "Create Database"
7. Una vez creada, ve a "Connections" y copia:
   - **Host**
   - **Port** (5432)
   - **Database**
   - **User**
   - **Password**

8. **Actualizar código para PostgreSQL** (pequeño cambio):
   - Cambiar `pymysql` por `psycopg2` en requirements.txt
   - El módulo `db_mysql.py` necesita adaptarse a PostgreSQL

**Nota**: PostgreSQL es muy similar a MySQL, solo cambian algunos detalles.

---

## 🥉 Opción 3: Supabase (PostgreSQL Gratis)

**URL**: https://supabase.com

### Ventajas:
- ✅ **100% GRATIS** (500MB, suficiente para empezar)
- ✅ PostgreSQL (muy potente)
- ✅ Dashboard muy bueno
- ✅ API REST automática

### Pasos:

1. **Crear cuenta**: https://supabase.com
2. **Crear proyecto nuevo**
3. **Ve a "Settings" → "Database"**
4. **Copia las credenciales** de "Connection string"
5. **En Render, agrega variables**:
   ```
   MYSQL_HOST=db.xxxxx.supabase.co
   MYSQL_PORT=5432
   MYSQL_USER=postgres
   MYSQL_PASSWORD=tu_password
   MYSQL_DATABASE=postgres
   ```

---

## 🏅 Opción 4: Neon (PostgreSQL Gratis)

**URL**: https://neon.tech

### Ventajas:
- ✅ **100% GRATIS** (512MB, suficiente)
- ✅ PostgreSQL serverless
- ✅ Muy rápido
- ✅ Auto-scaling

### Pasos:

1. **Crear cuenta**: https://neon.tech
2. **Crear proyecto**
3. **Copiar connection string**
4. **Configurar en Render** (similar a Supabase)

---

## 🎯 Recomendación Final

### Para empezar rápido: **Railway**
- Más fácil de configurar
- MySQL nativo (no necesitas cambiar código)
- $5 crédito mensual es más que suficiente

### Si quieres quedarte en Render: **Render PostgreSQL**
- Ya estás usando Render
- Gratis para siempre
- Solo necesitas adaptar el código a PostgreSQL

---

## 🔄 Adaptar código a PostgreSQL (si eliges Render/Supabase/Neon)

Si eliges PostgreSQL en lugar de MySQL, necesitas:

1. **Cambiar requirements.txt**:
   ```txt
   psycopg2-binary==2.9.9
   ```
   (en lugar de `pymysql`)

2. **Crear `db_postgresql.py`** (similar a `db_mysql.py` pero con `psycopg2`)

3. **Cambiar placeholders**: `%s` sigue funcionando en PostgreSQL

¿Quieres que te ayude a adaptar el código para PostgreSQL? Es muy rápido (5 minutos).

---

## 📊 Comparación Rápida

| Servicio | Tipo | Gratis | Dificultad | Recomendado |
|----------|------|--------|------------|-------------|
| **Railway** | MySQL | $5/mes crédito | ⭐ Fácil | ✅ Sí |
| **Render** | PostgreSQL | ✅ Sí | ⭐⭐ Media | ✅ Sí |
| **Supabase** | PostgreSQL | ✅ Sí | ⭐ Fácil | ✅ Sí |
| **Neon** | PostgreSQL | ✅ Sí | ⭐ Fácil | ✅ Sí |

---

## 🚀 Siguiente Paso

**Recomendación**: Usa **Railway con MySQL** porque:
1. No necesitas cambiar código
2. Es muy fácil de configurar
3. $5 crédito mensual es suficiente
4. MySQL funciona perfecto con el código actual

¿Quieres que te guíe paso a paso con Railway?

