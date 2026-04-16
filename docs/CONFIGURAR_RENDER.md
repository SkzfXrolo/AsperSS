# 🚀 Configurar Render.com - Pasos Exactos

## ✅ Ya tienes código en GitHub

Ahora sigue estos pasos en Render:

---

## 📋 Paso 1: Ejecutar Script de GitHub

Primero ejecuta el script que creé para subir tu código:

```bash
SUBIR_A_GITHUB.bat
```

Este script:
- Configura Git
- Agrega todos tus archivos
- Los sube a GitHub

---

## 📋 Paso 2: En Render.com

### 1. Click "New Web Service"

En la página de Render donde estás, click en la tarjeta **"Web Services"** (segunda de la primera fila).

### 2. Conectar Repositorio

- Te pedirá conectar con GitHub
- Autoriza Render si es necesario
- Selecciona el repositorio: **`aspersink-svg/aspersprojectsSS`**

### 3. Configuración IMPORTANTE

Llena estos campos:

**Básico:**
- **Name**: `aspers-web-app` (o el nombre que quieras)
- **Region**: Elige el más cercano (ej: `Oregon (US West)`)
- **Branch**: `main`

**⚠️ MUY IMPORTANTE:**
- **Root Directory**: `web_app`
  - Tu aplicación Flask está en la carpeta `web_app`
  - Si no pones esto, Render buscará archivos en la raíz y fallará

**Runtime:**
- **Runtime**: `Python 3` (selecciónalo del dropdown)

**Build & Deploy:**
- **Build Command**: 
  ```
  pip install -r requirements.txt
  ```
- **Start Command**: 
  ```
  gunicorn app:app --bind 0.0.0.0:$PORT
  ```

### 4. Variables de Entorno (Opcional)

Puedes agregar estas después si es necesario:
- `API_URL`: `http://localhost:5000`
- `SECRET_KEY`: (genera una con: `python -c "import secrets; print(secrets.token_hex(32))"`)

### 5. Crear Servicio

- Click en **"Create Web Service"** (botón azul/morado)
- Espera ~5 minutos mientras Render construye tu app

---

## ✅ Paso 3: ¡Listo!

Una vez completado:

1. Tu app estará en: `https://aspers-web-app.onrender.com`
   (o el nombre que hayas puesto)

2. **Esta URL es PERMANENTE** - Compártela con tus clientes

3. Si se "duerme" (después de 15 min sin uso), se despertará automáticamente en ~30 segundos cuando alguien la visite

---

## ⚠️ Si hay Errores

### Error: "Module not found"
**Solución:** Verifica que `web_app/requirements.txt` tenga:
```txt
flask==3.0.0
flask-cors==4.0.0
requests==2.31.0
gunicorn==21.2.0
```

### Error: "No such file or directory"
**Solución:** Verifica que **Root Directory** sea exactamente `web_app` (sin espacios, sin mayúsculas)

### Error: "Port already in use"
**Solución:** Asegúrate de usar `$PORT` en el Start Command

---

## 🎯 Resumen

1. ✅ Ejecuta `SUBIR_A_GITHUB.bat`
2. ✅ En Render: Click "New Web Service"
3. ✅ Conecta repositorio `aspersink-svg/aspersprojectsSS`
4. ✅ **Root Directory**: `web_app`
5. ✅ **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
6. ✅ Click "Create Web Service"
7. ✅ Espera 5 minutos
8. ✅ ¡URL permanente lista!

¿Listo para empezar?

