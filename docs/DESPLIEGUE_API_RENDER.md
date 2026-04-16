# 🚀 Desplegar API en Render

## Pasos para Desplegar la API en Render

### 1. Preparar el Repositorio

Asegúrate de que estos archivos estén en la carpeta `source/`:
- ✅ `api_server.py`
- ✅ `requirements.txt`
- ✅ `Procfile` (nuevo)
- ✅ `gunicorn_config.py` (nuevo)

### 2. Crear Nuevo Servicio en Render

1. **Ve a tu dashboard de Render:**
   - https://dashboard.render.com

2. **Clic en "New +" → "Web Service"**

3. **Conecta tu repositorio de GitHub:**
   - Selecciona el repositorio `aspersprojectsSS`
   - O conecta manualmente

### 3. Configurar el Servicio

#### Configuración Básica:

- **Name:** `aspers-api` (o el nombre que prefieras)
- **Region:** Elige la más cercana a tus usuarios
- **Branch:** `main` (o la rama que uses)
- **Root Directory:** `source` ⚠️ **IMPORTANTE: Debe ser `source` (sin barra inicial, sin punto)**
- **Runtime:** `Python 3`
- **Build Command:** 
  ```bash
  pip install -r requirements.txt
  ```
  ⚠️ **NO uses `cd source &&` si Root Directory = `source`**
- **Start Command:**
  ```bash
  gunicorn api_server:app --config gunicorn_config.py
  ```
  ⚠️ **NO uses `cd source &&` si Root Directory = `source`**

#### Plan:
- **Free:** Para empezar (se apaga después de inactividad)
- **Starter:** $7/mes (siempre activo)

### 4. Variables de Entorno

En la sección "Environment", agrega:

```
API_SECRET_KEY=tu-clave-secreta-muy-larga-y-segura
```

**⚠️ IMPORTANTE:** Genera una clave segura:
```python
import secrets
print(secrets.token_hex(32))
```

O usa una herramienta online para generar una clave aleatoria.

### 5. Desplegar

1. **Clic en "Create Web Service"**
2. **Espera a que termine el build** (puede tomar 2-5 minutos)
3. **Verifica que el servicio esté "Live"**

### 6. Obtener la URL de la API

Una vez desplegado, Render te dará una URL como:
```
https://aspers-api.onrender.com
```

**Guarda esta URL** - la necesitarás para configurar el servicio web.

### 7. Configurar el Servicio Web para Usar la API

En tu servicio web (el que ya tienes desplegado):

1. **Ve a "Environment"**
2. **Agrega la variable:**
   ```
   API_URL=https://aspers-api.onrender.com
   ```
   (Reemplaza con tu URL real)

3. **Reinicia el servicio web** (Render lo hará automáticamente)

### 8. Verificar que Funciona

1. **Prueba la API directamente:**
   ```
   https://aspers-api.onrender.com/api/statistics
   ```

2. **Verifica desde el panel web:**
   - Ve a tu panel web en Render
   - Intenta cargar estadísticas o escaneos
   - Debería funcionar correctamente

## Estructura de Archivos Necesaria

```
source/
├── api_server.py          # API principal
├── requirements.txt        # Dependencias Python
├── Procfile              # Comando de inicio para Render
├── gunicorn_config.py     # Configuración de Gunicorn
└── scanner_db.sqlite     # Base de datos (se crea automáticamente)
```

## Troubleshooting

### Error: "No module named 'gunicorn'"
**Solución:** Agrega `gunicorn` a `requirements.txt`:
```
gunicorn==21.2.0
```

### Error: "502 Bad Gateway"
**Posibles causas:**
1. La API no está iniciando correctamente
2. El puerto no está configurado bien
3. La base de datos tiene problemas

**Solución:**
- Revisa los logs en Render
- Verifica que `Procfile` esté correcto
- Asegúrate de que `gunicorn_config.py` use `PORT` de Render

### Error: "Database locked"
**Solución:** 
- SQLite puede tener problemas con múltiples workers
- Reduce workers en `gunicorn_config.py`:
  ```python
  workers = 1  # Para SQLite, 1 worker es más seguro
  ```

### La API se apaga después de inactividad
**Solución:**
- Esto es normal en el plan gratuito
- Usa UptimeRobot o GitHub Actions para mantenerla despierta
- O actualiza a un plan de pago

## Health Check

Render necesita un endpoint de health check. La API ya tiene endpoints que funcionan:
- `/api/statistics` (requiere autenticación)
- Cualquier endpoint que devuelva 200

Puedes agregar un endpoint simple de health check si es necesario.

## Costos

- **Free Plan:** Gratis, pero se apaga después de 15 minutos de inactividad
- **Starter Plan:** $7/mes, siempre activo
- **Pro Plan:** $25/mes, más recursos

## Próximos Pasos

1. ✅ Despliega la API en Render
2. ✅ Obtén la URL de la API
3. ✅ Configura `API_URL` en el servicio web
4. ✅ Verifica que todo funcione
5. ✅ (Opcional) Configura UptimeRobot para mantenerla despierta

## Notas Importantes

- ⚠️ **Root Directory debe ser `source`** - No dejes el default
- ⚠️ **La base de datos SQLite se reinicia** en cada deploy en el plan gratuito
- ⚠️ **Usa un plan de pago** si necesitas persistencia de datos
- ⚠️ **Guarda la API Key** de forma segura - la necesitarás para el servicio web

