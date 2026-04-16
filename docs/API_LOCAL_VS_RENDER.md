# 🔌 API: Local vs Render - Explicación Clara

## 📋 Resumen Rápido

- **Desarrollo Local**: La API corre en `localhost:5000` en tu PC
- **Render (Producción)**: La API debe estar desplegada como un servicio separado en Render

---

## 🏠 Desarrollo Local (Tu PC)

### Cómo Funciona:

1. **Ejecutas la API localmente:**
   ```bash
   cd source
   python api_server.py
   ```
   - La API corre en: `http://localhost:5000`

2. **Ejecutas el servidor web localmente:**
   ```bash
   cd web_app
   python app.py
   ```
   - El servidor web corre en: `http://localhost:8080`
   - Se conecta a la API en `localhost:5000`

### ✅ Ventajas:
- Rápido para desarrollo
- Fácil de debuggear
- No necesitas internet (después de instalar dependencias)

### ❌ Desventajas:
- Solo funciona en tu PC
- Tienes que tener ambos servicios corriendo
- No está disponible para otros usuarios

---

## ☁️ Render (Producción - En la Nube)

### Cómo Funciona:

1. **Servicio 1: API** (`aspers-api`)
   - Desplegado en Render como servicio separado
   - URL: `https://aspers-api.onrender.com`
   - Corre 24/7 en la nube

2. **Servicio 2: Web App** (`aspers-web-app`)
   - Desplegado en Render como servicio separado
   - URL: `https://aspersprojectsss.onrender.com`
   - Se conecta a la API usando la URL: `https://aspers-api.onrender.com`

### ✅ Ventajas:
- Disponible 24/7
- Accesible desde cualquier lugar
- No necesitas tener tu PC encendida
- Ambos servicios corren independientemente

### ❌ Desventajas:
- Requiere configuración inicial
- Plan gratuito se "duerme" después de 15 min de inactividad

---

## 🎯 Configuración Actual

### En Desarrollo Local:
```python
# app.py detecta automáticamente que NO estás en Render
API_BASE_URL = 'http://localhost:5000'  # API local
```

### En Render:
```python
# app.py detecta automáticamente que estás en Render
# Si tienes API_URL configurado:
API_BASE_URL = 'https://aspers-api.onrender.com'  # API en Render

# Si NO tienes API_URL configurado:
API_BASE_URL = 'https://aspersprojectsss.onrender.com'  # Misma URL base
```

---

## ✅ Qué Necesitas Hacer

### Opción A: Desplegar API en Render (Recomendado)

1. **Crea servicio API en Render:**
   - Name: `aspers-api`
   - Root Directory: `source`
   - Start Command: `python api_server.py`
   - Build Command: `pip install -r ../web_app/requirements.txt`

2. **Obtén la URL de la API:**
   - Ejemplo: `https://aspers-api.onrender.com`

3. **Configura en el servicio web:**
   - Variable de entorno: `API_URL` = `https://aspers-api.onrender.com`

4. **¡Listo!** Ambos servicios funcionan independientemente

### Opción B: Usar Solo el Servicio Web (Si no necesitas la API externa)

Si tu aplicación web no necesita conectarse a `api_server.py` (porque toda la funcionalidad está en `app.py` y `auth.py`), entonces:

- ✅ **No necesitas desplegar la API**
- ✅ Solo despliega el servicio web
- ✅ Todo funciona desde un solo servicio

---

## 🔍 ¿Cómo Saber si Necesitas la API?

### Necesitas desplegar la API si:
- ❌ Tu aplicación web intenta conectarse a `/api/tokens`, `/api/scans`, etc.
- ❌ Ves errores como "No se pudo conectar a la API"
- ❌ Funciones como crear tokens no funcionan

### NO necesitas desplegar la API si:
- ✅ Todo funciona correctamente
- ✅ Los tokens se crean sin problemas
- ✅ No ves errores de conexión a la API

---

## 📊 Comparación Visual

### Desarrollo Local:
```
Tu PC:
├── API (localhost:5000) ← Corre en tu PC
└── Web App (localhost:8080) ← Se conecta a localhost:5000
```

### Render (Producción):
```
Render Cloud:
├── Servicio 1: API (aspers-api.onrender.com) ← Corre en la nube
└── Servicio 2: Web App (aspersprojectsss.onrender.com) ← Se conecta a aspers-api.onrender.com
```

---

## 🚀 Pasos para Desplegar la API en Render

### 1. Crear Servicio API

1. Ve a Render.com
2. Click **"New +"** → **"Web Service"**
3. Conecta repositorio: `aspersink-svg/aspersprojectsSS`
4. Configura:
   - **Name**: `aspers-api`
   - **Root Directory**: `source`
   - **Start Command**: `python api_server.py`
   - **Build Command**: `pip install -r ../web_app/requirements.txt`
5. Click **"Create Web Service"**

### 2. Configurar Variables de Entorno (API)

En el servicio API, agrega:
- `API_SECRET_KEY`: (genera una)
- `DATABASE`: `scanner_db.sqlite`

### 3. Obtener URL de la API

Una vez desplegado, copia la URL:
- Ejemplo: `https://aspers-api.onrender.com`

### 4. Configurar Servicio Web

En tu servicio web (`aspers-web-app`):
1. Ve a **"Environment"**
2. Agrega variable:
   - **Key**: `API_URL`
   - **Value**: `https://aspers-api.onrender.com`
3. Guarda cambios

### 5. ¡Listo!

Ahora ambos servicios funcionan independientemente en Render.

---

## ⚠️ Nota Importante sobre la Base de Datos

**SQLite no funciona bien con múltiples servicios** porque cada servicio tiene su propio sistema de archivos.

### Soluciones:

1. **Usar PostgreSQL** (Recomendado)
   - Crea una base de datos PostgreSQL en Render
   - Ambos servicios se conectan a la misma BD

2. **Solo API escribe** (Solución rápida)
   - Solo la API escribe en SQLite
   - El servicio web solo lee (a través de la API)
   - Esto funciona con SQLite

---

## 🆘 ¿Necesitas Ayuda?

- **¿No sabes si necesitas la API?** Revisa los logs de tu aplicación web
- **¿La API no inicia?** Revisa los logs del servicio API en Render
- **¿Errores de conexión?** Verifica que `API_URL` esté configurado correctamente

---

**Resumen:** En Render, NO necesitas correr la API localmente. Debe estar desplegada como un servicio separado en la nube.

