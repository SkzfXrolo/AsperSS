# 🚀 Pasos para Deploy en Render.com - Guía Rápida

## ✅ Estás en la página correcta

Veo que estás en Render.com. Sigue estos pasos:

---

## 📋 Paso 1: Crear Web Service

1. **Click en "New Web Service"** (la tarjeta con el globo)
   - Es la segunda tarjeta de la primera fila
   - Dice "Dynamic web app. Ideal for full-stack apps, API servers, and mobile backends."

---

## 📋 Paso 2: Conectar Repositorio

**IMPORTANTE:** Primero necesitas tener tu código en GitHub.

### Si NO tienes código en GitHub todavía:

#### Opción A: Subir ahora (rápido)

1. Abre PowerShell o CMD en tu carpeta del proyecto:
   ```bash
   cd "C:\Users\robin\Desktop\Tareas\Aplicación de SS"
   ```

2. Inicializa Git (si no lo has hecho):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

3. Crea repositorio en GitHub:
   - Ve a: https://github.com/new
   - Nombre: `aspers-web-app` (o el que quieras)
   - **NO** marques "Initialize with README"
   - Click "Create repository"

4. Conecta y sube:
   ```bash
   git remote add origin https://github.com/TU_USUARIO/aspers-web-app.git
   git branch -M main
   git push -u origin main
   ```
   (Reemplaza `TU_USUARIO` con tu usuario de GitHub)

#### Opción B: Usar Render sin GitHub (más adelante)

Puedes hacer deploy manual subiendo archivos, pero es más complicado.

---

## 📋 Paso 3: Configurar en Render

Una vez conectado tu repositorio:

### Configuración Básica:

1. **Name**: `aspers-web-app` (o el nombre que quieras)

2. **Region**: Elige el más cercano (ej: `Oregon (US West)`)

3. **Branch**: `main` (o `master` si usas esa rama)

4. **Root Directory**: `web_app` ⚠️ **MUY IMPORTANTE**
   - Tu aplicación Flask está en la carpeta `web_app`
   - Si no pones esto, Render buscará archivos en la raíz y fallará

5. **Runtime**: `Python 3` (selecciónalo del dropdown)

6. **Build Command**: 
   ```
   pip install -r requirements.txt
   ```

7. **Start Command**: 
   ```
   gunicorn app:app --bind 0.0.0.0:$PORT
   ```

### Variables de Entorno (Opcional por ahora):

Puedes agregarlas después si es necesario:
- `API_URL`: `http://localhost:5000` (o la URL de tu API)
- `SECRET_KEY`: Genera una con: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## 📋 Paso 4: Crear el Servicio

1. **Click en "Create Web Service"** (botón azul/morado abajo)

2. **Espera ~5 minutos** mientras Render:
   - Descarga tu código
   - Instala dependencias
   - Construye la aplicación
   - La despliega

3. **Verás logs en tiempo real** - Puedes ver qué está pasando

---

## ✅ Paso 5: ¡Listo!

Una vez completado:

1. Tu app estará en: `https://aspers-web-app.onrender.com`
   (o el nombre que hayas puesto)

2. **Comparte esta URL con tus clientes** - Siempre será la misma

3. Si se "duerme" (después de 15 min sin uso), se despertará automáticamente en ~30 segundos cuando alguien la visite

---

## ⚠️ Problemas Comunes

### Error: "Module not found"
**Solución:** Verifica que `requirements.txt` tenga todas las dependencias:
```txt
flask==3.0.0
flask-cors==4.0.0
requests==2.31.0
gunicorn==21.2.0
```

### Error: "No such file or directory"
**Solución:** Verifica que **Root Directory** sea `web_app`

### Error: "Port already in use"
**Solución:** Asegúrate de usar `$PORT` en el Start Command (Render lo asigna automáticamente)

---

## 💡 ¿Necesitas Ayuda?

Si tienes algún error durante el deploy:
1. Revisa los logs en Render (te muestran el error exacto)
2. Compárteme el error y te ayudo a solucionarlo

---

## 🎯 Resumen Rápido

1. ✅ Click "New Web Service"
2. ✅ Conecta tu repositorio de GitHub
3. ✅ **Root Directory**: `web_app`
4. ✅ **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. ✅ Click "Create Web Service"
6. ✅ Espera 5 minutos
7. ✅ ¡Listo! URL permanente para tus clientes

¿Tienes tu código en GitHub ya o necesitas ayuda para subirlo?

