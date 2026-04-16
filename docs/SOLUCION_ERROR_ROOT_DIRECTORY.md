# 🔧 Solución: Error Root Directory en Render

## Error

```
Service Root Directory "/opt/render/project/src/source" is missing.
builder.sh: line 51: cd: /opt/render/project/src/source: No such file or directory
```

## Causa

El **Root Directory** está mal configurado en Render. Render está buscando en una ruta incorrecta.

## Solución

### Paso 1: Verificar la Estructura del Repositorio

Tu repositorio debe tener esta estructura:
```
aspersprojectsSS/
├── source/
│   ├── api_server.py
│   ├── requirements.txt
│   ├── Procfile
│   └── gunicorn_config.py
├── web_app/
└── ...
```

### Paso 2: Configurar Root Directory Correctamente

1. **Ve a tu servicio en Render Dashboard**

2. **Haz clic en "Settings"** (Configuración)

3. **Busca la sección "Build & Deploy"**

4. **En "Root Directory"**, escribe **EXACTAMENTE** esto:
   ```
   source
   ```
   
   ⚠️ **IMPORTANTE:**
   - ❌ NO uses: `/source`
   - ❌ NO uses: `./source`
   - ❌ NO uses: `source/`
   - ✅ SÍ usa: `source` (solo la palabra, sin barras)

5. **Guarda los cambios** (haz clic en "Save Changes")

6. **Render reiniciará automáticamente** el build

### Paso 3: Verificar Otras Configuraciones

Asegúrate de que estas configuraciones estén correctas:

- **Build Command:**
  ```
  pip install -r requirements.txt
  ```

- **Start Command:**
  ```
  gunicorn api_server:app --config gunicorn_config.py
  ```

### Paso 4: Si el Error Persiste

#### Opción A: Dejar Root Directory Vacío

1. **Borra el contenido de "Root Directory"** (déjalo vacío)

2. **Actualiza el Build Command:**
   ```
   cd source && pip install -r requirements.txt
   ```

3. **Actualiza el Start Command:**
   ```
  cd source && gunicorn api_server:app --config gunicorn_config.py
  ```

#### Opción B: Mover Archivos a la Raíz

Si prefieres, puedes mover los archivos necesarios a la raíz del repositorio:

1. **Crea estos archivos en la raíz:**
   - `Procfile` (copiado de `source/Procfile`)
   - `requirements.txt` (copiado de `source/requirements.txt`)
   - `gunicorn_config.py` (copiado de `source/gunicorn_config.py`)

2. **Actualiza el Procfile** para que apunte a `source/api_server.py`:
   ```
   web: cd source && gunicorn api_server:app --config ../gunicorn_config.py
   ```

3. **Deja Root Directory vacío** en Render

## Verificación

Después de corregir, verifica:

1. **Los logs de Render** deberían mostrar:
   ```
   Installing dependencies...
   Starting gunicorn...
   ```

2. **El servicio debería estar "Live"** (verde)

3. **La URL de la API debería responder** (ej: `https://aspers-api.onrender.com/api/statistics`)

## Estructura Correcta en GitHub

Asegúrate de que en GitHub, la estructura sea:

```
aspersprojectsSS/
├── source/
│   ├── api_server.py          ✅
│   ├── requirements.txt        ✅
│   ├── Procfile                ✅
│   └── gunicorn_config.py      ✅
└── ...
```

## Notas Importantes

- ⚠️ **Root Directory es relativo** a la raíz del repositorio
- ⚠️ **No uses rutas absolutas** como `/source` o `./source`
- ⚠️ **Render clona el repo en** `/opt/render/project/src/`
- ⚠️ **Si Root Directory = `source`**, Render buscará en `/opt/render/project/src/source`

## Si Nada Funciona

1. **Elimina el servicio** en Render
2. **Crea un nuevo servicio** desde cero
3. **Configura Root Directory = `source`** (sin barras)
4. **Configura Build y Start commands** correctamente

