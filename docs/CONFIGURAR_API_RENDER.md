# 🚀 Configurar API en Render - Guía Rápida

## 📋 Problema Resuelto

He actualizado el código para que funcione correctamente en Render. Ahora necesitas desplegar la API como un servicio separado.

---

## ✅ Pasos para Configurar

### Paso 1: Desplegar la API

1. **Ve a Render.com** → Click **"New +"** → **"Web Service"**

2. **Conecta el repositorio:**
   - Selecciona: `aspersink-svg/aspersprojectsSS`

3. **Configuración del servicio API:**
   ```
   Name: aspers-api
   Root Directory: source
   Start Command: python api_server.py
   Build Command: pip install -r ../web_app/requirements.txt
   ```

4. **Variables de entorno (Environment Variables):**
   ```
   API_SECRET_KEY: [genera una con: python -c "import secrets; print(secrets.token_hex(32))"]
   DATABASE: scanner_db.sqlite
   ```

5. **Click "Create Web Service"**

6. **Espera ~5 minutos** mientras Render despliega

7. **Copia la URL de la API** (ej: `https://aspers-api.onrender.com`)

---

### Paso 2: Configurar el Servicio Web

1. **Ve a tu servicio web** (`aspers-web-app`)

2. **Click en "Environment"** (en el menú lateral)

3. **Agrega variable de entorno:**
   ```
   Key: API_URL
   Value: https://aspers-api.onrender.com
   ```
   (Reemplaza con la URL real de tu API)

4. **Click "Save Changes"**

5. **Render reiniciará automáticamente** el servicio

---

### Paso 3: Verificar que Funciona

1. **Ve a tu aplicación web:** `https://aspers-web-app.onrender.com`

2. **Inicia sesión**

3. **Intenta crear un token**

4. **Si funciona, ¡listo!** ✅

---

## ⚠️ Nota Importante sobre la Base de Datos

**SQLite no funciona bien con múltiples servicios** en Render porque cada servicio tiene su propio sistema de archivos.

### Opción A: Usar PostgreSQL (Recomendado para producción)

1. En Render, crea una base de datos PostgreSQL
2. Actualiza `api_server.py` para usar PostgreSQL en lugar de SQLite
3. Configura la URL de conexión en las variables de entorno

### Opción B: Solo un servicio escribe (Solución rápida)

- Solo la API escribe en la base de datos
- El servicio web solo lee (a través de la API)
- Esto funciona con SQLite

---

## 🎯 Resumen

1. ✅ Despliega la API como servicio separado (`aspers-api`)
2. ✅ Configura `API_URL` en el servicio web con la URL de la API
3. ✅ Guarda y espera el reinicio
4. ✅ ¡Listo!

---

## 🆘 Si tienes problemas

1. **Revisa los logs** en Render para ver errores específicos
2. **Verifica que la API esté corriendo** visitando: `https://aspers-api.onrender.com/api/versions`
3. **Confirma las variables de entorno** en ambos servicios
4. **Asegúrate de que ambos servicios estén en la misma región**

---

**¿Necesitas ayuda?** Revisa `SOLUCION_ERROR_API_RENDER.md` para más detalles.


