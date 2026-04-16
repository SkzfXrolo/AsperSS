# 🚀 Desplegar en Render.com - Guía Rápida

## ✅ Tu código ya está en GitHub

Veo que tu proyecto está en: https://github.com/aspersink-svg/aspersprojectsSS

Ahora vamos a desplegarlo en Render.com para que esté en línea con una URL permanente.

---

## 📋 Paso 1: Ir a Render.com

1. **Ve a:** https://render.com
2. **Inicia sesión** (o crea cuenta gratis con GitHub)
3. **Click en "New +"** (arriba a la derecha)
4. **Click en "Web Service"**

---

## 📋 Paso 2: Conectar con GitHub

1. Render te pedirá conectar con GitHub
2. **Click en "Connect GitHub"** o **"Connect account"**
3. **Autoriza Render** para acceder a tus repositorios
4. **Selecciona el repositorio:** `aspersink-svg/aspersprojectsSS`
5. **Click en "Connect"**

---

## 📋 Paso 3: Configuración IMPORTANTE

Llena estos campos **EXACTAMENTE** como se muestra:

### Información Básica:

- **Name**: `aspers-web-app`
  - (O el nombre que prefieras, será parte de tu URL)

- **Region**: Elige el más cercano
  - Ejemplo: `Oregon (US West)` o `Frankfurt (EU Central)`

- **Branch**: `main`
  - (Debería estar seleccionado por defecto)

### ⚠️ CONFIGURACIÓN CRÍTICA:

- **Root Directory**: `web_app`
  - ⚠️ **MUY IMPORTANTE** - Tu aplicación Flask está dentro de la carpeta `web_app`
  - Si no pones esto, Render buscará `app.py` en la raíz y fallará

### Runtime:

- **Runtime**: `Python 3`
  - (Selecciónalo del dropdown)

### Build & Deploy:

- **Build Command**: 
  ```
  pip install -r requirements.txt
  ```
  - (Render instalará las dependencias automáticamente)

- **Start Command**: 
  ```
  gunicorn app:app --bind 0.0.0.0:$PORT
  ```
  - ⚠️ **IMPORTANTE**: Usa `$PORT` (Render lo asigna automáticamente)

---

## 📋 Paso 4: Variables de Entorno (Opcional)

Por ahora puedes dejarlo vacío. Si necesitas agregar variables después:

- **Environment Variables**: (Click en "Advanced")
  - `API_URL`: `http://localhost:5000` (si tu API está en otro lugar)
  - `SECRET_KEY`: (genera una con: `python -c "import secrets; print(secrets.token_hex(32))"`)

---

## 📋 Paso 5: Crear el Servicio

1. **Revisa que todo esté correcto:**
   - ✅ Root Directory: `web_app`
   - ✅ Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - ✅ Build Command: `pip install -r requirements.txt`

2. **Click en "Create Web Service"** (botón azul/morado abajo)

3. **Espera ~5 minutos** mientras Render:
   - Descarga tu código de GitHub
   - Instala las dependencias de `requirements.txt`
   - Construye la aplicación
   - La despliega en línea

4. **Verás logs en tiempo real** - Puedes ver qué está pasando paso a paso

---

## ✅ Paso 6: ¡Listo!

Una vez completado el deploy:

1. **Tu app estará en:** `https://aspers-web-app.onrender.com`
   - (O el nombre que hayas puesto)

2. **Esta URL es PERMANENTE** - Compártela con tus clientes

3. **Si se "duerme"** (después de 15 min sin uso):
   - Se despertará automáticamente en ~30 segundos cuando alguien la visite
   - Es normal en el plan gratuito

---

## ⚠️ Problemas Comunes y Soluciones

### Error: "Module not found: flask"

**Solución:** Verifica que `web_app/requirements.txt` tenga:
```txt
flask==3.0.0
flask-cors==4.0.0
requests==2.31.0
gunicorn==21.2.0
```

### Error: "No such file or directory: app.py"

**Solución:** 
- Verifica que **Root Directory** sea exactamente `web_app` (sin espacios, sin mayúsculas)
- Asegúrate de que `app.py` esté dentro de `web_app/`

### Error: "Port already in use"

**Solución:** 
- Asegúrate de usar `$PORT` en el Start Command (no un número fijo)
- Render asigna el puerto automáticamente

### Error: "Build failed"

**Solución:**
- Revisa los logs en Render (te muestran el error exacto)
- Verifica que `requirements.txt` tenga todas las dependencias
- Asegúrate de que el Root Directory sea correcto

---

## 🎯 Resumen Visual

```
1. Render.com → "New +" → "Web Service"
2. Conecta GitHub → Selecciona "aspersink-svg/aspersprojectsSS"
3. Name: aspers-web-app
4. Root Directory: web_app ⚠️
5. Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
6. Build Command: pip install -r requirements.txt
7. Click "Create Web Service"
8. Espera 5 minutos
9. ✅ URL permanente lista!
```

---

## 💡 Después del Deploy

Una vez que tu app esté funcionando:

1. **Prueba la URL:** Abre `https://aspers-web-app.onrender.com` en tu navegador
2. **Comparte con clientes:** Esta URL siempre será la misma
3. **Monitorea logs:** En Render puedes ver logs en tiempo real
4. **Actualiza código:** Cada vez que hagas push a GitHub, Render actualizará automáticamente

---

## 🆘 ¿Necesitas Ayuda?

Si encuentras algún error durante el deploy:

1. **Revisa los logs** en Render (te muestran el error exacto)
2. **Compárteme el error** y te ayudo a solucionarlo
3. **Verifica** que `web_app/requirements.txt` tenga todas las dependencias

---

## ✅ Checklist Final

Antes de hacer deploy, verifica:

- [ ] Tu código está en GitHub: https://github.com/aspersink-svg/aspersprojectsSS
- [ ] `web_app/app.py` existe
- [ ] `web_app/requirements.txt` tiene todas las dependencias
- [ ] `web_app/Procfile` existe (opcional, pero recomendado)
- [ ] Root Directory será: `web_app`
- [ ] Start Command será: `gunicorn app:app --bind 0.0.0.0:$PORT`

---

**¿Listo para desplegar?** Ve a Render.com y sigue los pasos. Si tienes algún problema, dime qué error ves y te ayudo.


