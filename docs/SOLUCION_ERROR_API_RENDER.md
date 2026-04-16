# 🔧 Solución: Error de Conexión a la API en Render

## ❌ Problema

Cuando intentas crear un token o usar funciones del panel en Render, aparece el error:

```
Error al crear token: No se pudo conectar a la API. Verifica que esté corriendo en http://localhost:5000
```

## 🔍 Causa

En Render, la aplicación web (`app.py`) intenta conectarse a la API (`api_server.py`) en `localhost:5000`, pero en Render no existe `localhost` - cada servicio tiene su propia URL.

## ✅ Solución: Dos Opciones

### Opción 1: Desplegar la API como Servicio Separado (Recomendado)

1. **En Render, crea un segundo servicio:**
   - Ve a tu dashboard de Render
   - Click en **"New +"** → **"Web Service"**
   - Conecta el mismo repositorio: `aspersink-svg/aspersprojectsSS`

2. **Configuración del servicio de API:**
   - **Name**: `aspers-api`
   - **Root Directory**: `source` (no `web_app`)
   - **Start Command**: `python api_server.py`
   - **Build Command**: `pip install -r ../web_app/requirements.txt`
   - **Environment Variables**:
     - `API_SECRET_KEY`: (genera una con: `python -c "import secrets; print(secrets.token_hex(32))"`)
     - `DATABASE`: `scanner_db.sqlite`

3. **Obtén la URL de la API:**
   - Una vez desplegado, Render te dará una URL como: `https://aspers-api.onrender.com`
   - Copia esta URL

4. **Configura la variable de entorno en el servicio web:**
   - Ve a tu servicio web (`aspers-web-app`)
   - Click en **"Environment"**
   - Agrega variable:
     - **Key**: `API_URL`
     - **Value**: `https://aspers-api.onrender.com` (la URL de tu API)
   - Click **"Save Changes"**
   - Render reiniciará automáticamente

5. **¡Listo!** Ahora la aplicación web se conectará a la API correctamente.

---

### Opción 2: Integrar la API en el mismo Servicio (Más Simple)

Esta opción hace que `app.py` también sirva los endpoints de la API directamente.

**Pasos:**

1. **Crea un archivo `web_app/api_routes.py`** que importe las funciones de `api_server.py`

2. **Modifica `web_app/app.py`** para registrar las rutas de la API cuando está en Render

3. **Asegúrate de que la base de datos esté disponible** en Render

**Nota:** Esta opción requiere más cambios en el código. La Opción 1 es más simple y recomendada.

---

## 🚀 Pasos Rápidos (Opción 1)

1. ✅ Crea servicio API en Render: `aspers-api`
2. ✅ Root Directory: `source`
3. ✅ Start Command: `python api_server.py`
4. ✅ Obtén URL de la API (ej: `https://aspers-api.onrender.com`)
5. ✅ Agrega variable `API_URL` en el servicio web con la URL de la API
6. ✅ Guarda y espera el reinicio

---

## ⚠️ Importante

- **Base de datos compartida:** Si ambos servicios necesitan la misma base de datos, considera usar una base de datos externa (PostgreSQL) en lugar de SQLite, ya que SQLite no funciona bien con múltiples servicios.

- **Alternativa rápida:** Puedes usar SQLite si solo uno de los servicios escribe en la base de datos. En ese caso, configura la API para leer/escribir y el web solo para leer.

---

## 🆘 Si sigues teniendo problemas

1. **Verifica los logs** en Render para ver errores específicos
2. **Confirma que la API está corriendo** visitando `https://aspers-api.onrender.com/api/versions`
3. **Verifica las variables de entorno** en ambos servicios
4. **Asegúrate de que ambos servicios estén en la misma región** de Render

---

## 📝 Resumen

**Problema:** La app web intenta conectarse a `localhost:5000` que no existe en Render.

**Solución:** Despliega la API como servicio separado y configura `API_URL` en el servicio web.

**Resultado:** Ambos servicios funcionan correctamente en Render.


