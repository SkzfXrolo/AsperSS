# 🚀 Deploy en Render.com - Guía Completa

## ✅ Render.com SÍ funciona para Flask

Render.com es perfecto para tu aplicación Flask. Te guío paso a paso.

---

## 📋 Requisitos Previos

1. ✅ Cuenta en GitHub (gratis)
2. ✅ Tu código en un repositorio de GitHub
3. ✅ Cuenta en Render.com (gratis)

---

## 🔧 Paso 1: Preparar tu Aplicación

### 1.1 Crear `Procfile`

Crea un archivo `Procfile` en la carpeta `web_app/`:

```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

### 1.2 Actualizar `requirements.txt`

Asegúrate de que `requirements.txt` incluya `gunicorn`:

```txt
flask==3.0.0
flask-cors==4.0.0
requests==2.31.0
gunicorn==21.2.0
```

### 1.3 Crear `runtime.txt` (opcional)

Si quieres especificar la versión de Python:

```
python-3.11.0
```

### 1.4 Ajustar configuración para producción

Render usa variables de entorno. Tu código ya las usa (`os.environ.get`), así que está bien.

---

## 📤 Paso 2: Subir a GitHub

### 2.1 Inicializar repositorio (si no lo tienes)

```bash
cd "C:\Users\robin\Desktop\Tareas\Aplicación de SS"
git init
git add .
git commit -m "Initial commit"
```

### 2.2 Crear repositorio en GitHub

1. Ve a: https://github.com/new
2. Crea un repositorio nuevo (ej: `aspers-web-app`)
3. **NO** inicialices con README

### 2.3 Subir código

```bash
git remote add origin https://github.com/TU_USUARIO/aspers-web-app.git
git branch -M main
git push -u origin main
```

---

## 🚀 Paso 3: Deploy en Render

### 3.1 Crear cuenta

1. Ve a: https://render.com
2. Click "Get Started for Free"
3. Conecta con GitHub

### 3.2 Crear Web Service

1. Click "New" → "Web Service"
2. Conecta tu repositorio de GitHub
3. Selecciona el repositorio `aspers-web-app`

### 3.3 Configurar el servicio

**Configuración básica:**
- **Name**: `aspers-web-app` (o el que quieras)
- **Region**: `Oregon (US West)` (o el más cercano)
- **Branch**: `main`
- **Root Directory**: `web_app` (IMPORTANTE: tu app está en esta carpeta)
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`

**Variables de entorno:**
- `API_URL`: `http://localhost:5000` (o la URL de tu API si está en otro lado)
- `SECRET_KEY`: Genera una clave secreta (usa: `python -c "import secrets; print(secrets.token_hex(32))"`)
- `FLASK_ENV`: `production`

### 3.4 Crear Base de Datos PostgreSQL (Opcional)

Si quieres migrar de SQLite a PostgreSQL:

1. "New" → "PostgreSQL"
2. Nombre: `aspers-db`
3. Plan: Free
4. Copia la "Internal Database URL"
5. Agrega variable de entorno: `DATABASE_URL`

**Nota:** SQLite funciona en Render, pero los datos se pierden al reiniciar. PostgreSQL es persistente.

### 3.5 Deploy

1. Click "Create Web Service"
2. Espera ~5 minutos
3. Render construye y despliega tu app
4. Verás logs en tiempo real

---

## ✅ Paso 4: Verificar

Una vez completado el deploy:

1. Tu app estará en: `https://aspers-web-app.onrender.com`
2. Prueba acceder a la URL
3. Si hay errores, revisa los logs en Render

---

## 🔧 Solución de Problemas Comunes

### Error: "Module not found"

**Solución:** Verifica que `requirements.txt` incluya todas las dependencias.

### Error: "Port already in use"

**Solución:** Asegúrate de usar `$PORT` en el comando de inicio (Render lo asigna automáticamente).

### Error: "Database locked" (SQLite)

**Solución:** SQLite puede tener problemas en Render. Considera:
1. Usar PostgreSQL (gratis en Render)
2. O usar Cloudflare Tunnel (tu PC)

### La app se "duerme"

**Solución:** Es normal en el plan gratis. Se despierta automáticamente en ~30 segundos cuando alguien la visita.

---

## 💡 Mejoras Opcionales

### 1. Usar PostgreSQL en lugar de SQLite

Render ofrece PostgreSQL gratis. Puedo ayudarte a migrar tu código.

### 2. Configurar dominio personalizado

1. En Render: Settings → Custom Domain
2. Agrega tu dominio (ej: `aspersprojects.tk`)
3. Configura DNS según las instrucciones

### 3. Auto-deploy desde GitHub

Render hace auto-deploy automáticamente cuando haces push a GitHub.

---

## 📊 Comparación: Render vs Cloudflare Tunnel

| Característica | Render.com | Cloudflare Tunnel |
|----------------|-------------|-------------------|
| **Costo** | Gratis | Gratis |
| **Se duerme** | ⚠️ Sí (15 min) | ❌ No |
| **Requiere PC encendido** | ❌ No | ✅ Sí |
| **URL permanente** | ✅ Sí | ✅ Sí (con dominio) |
| **Base de datos** | ✅ PostgreSQL gratis | ⚠️ SQLite local |
| **Fácil de usar** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 🎯 Recomendación

**Para producción:** Render.com (más profesional, siempre disponible)

**Para desarrollo:** Cloudflare Tunnel (ya lo tienes funcionando)

---

## ❓ ¿Necesitas ayuda?

Puedo ayudarte a:
1. Crear los archivos necesarios (`Procfile`, `requirements.txt` actualizado)
2. Configurar variables de entorno
3. Migrar de SQLite a PostgreSQL (si quieres)
4. Hacer el deploy paso a paso

¿Quieres que prepare todo para Render ahora?

