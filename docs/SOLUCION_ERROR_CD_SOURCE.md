# 🔧 Solución: Error "cd: source: No such file or directory" en Render

## Error

```
==> Running build command 'cd source && pip install -r requirements.txt'...
bash: line 1: cd: source: No such file or directory
==> Build failed 😞
```

## Causa

Hay un conflicto entre el **Root Directory** y el **Build Command**. 

Si el Root Directory está configurado como `source`, entonces Render YA está dentro de la carpeta `source/`, por lo que NO debes usar `cd source &&` en el Build Command.

## Solución

Tienes **2 opciones**:

### Opción 1: Root Directory = "source" (RECOMENDADO)

**Configuración en Render:**

1. **Root Directory:** `source` (solo la palabra, sin barras)

2. **Build Command:** 
   ```
   pip install -r requirements.txt
   ```
   ⚠️ **SIN** `cd source &&`

3. **Start Command:**
   ```
   gunicorn api_server:app --config gunicorn_config.py
   ```
   ⚠️ **SIN** `cd source &&`

**¿Por qué?** Porque si Root Directory = `source`, Render ya está ejecutando los comandos dentro de `source/`, así que no necesitas cambiar de directorio.

---

### Opción 2: Root Directory vacío

**Configuración en Render:**

1. **Root Directory:** (dejar VACÍO)

2. **Build Command:**
   ```
   cd source && pip install -r requirements.txt
   ```

3. **Start Command:**
   ```
   cd source && gunicorn api_server:app --config gunicorn_config.py
   ```

**¿Por qué?** Porque si Root Directory está vacío, Render está en la raíz del repositorio, así que SÍ necesitas cambiar a `source/`.

---

## Verificar que source/ está en GitHub

**ANTES de configurar Render**, verifica que la carpeta `source/` esté en GitHub:

1. Ve a: `https://github.com/aspersink-svg/aspersprojectsSS/tree/main`
2. Debes ver la carpeta `source/`
3. Dentro debe haber:
   - `api_server.py`
   - `requirements.txt`
   - `Procfile`
   - `gunicorn_config.py`

**Si NO está en GitHub**, súbela primero:
```bash
git add source/
git commit -m "Agregar carpeta source con archivos de API"
git push
```

---

## Configuración Correcta (Recomendada)

### En Render Dashboard → Settings:

```
Root Directory: source
Build Command: pip install -r requirements.txt
Start Command: gunicorn api_server:app --config gunicorn_config.py
```

### Variables de Entorno:

```
API_SECRET_KEY = [tu-clave-secreta]
```

---

## Pasos para Corregir Ahora

1. **Ve a Render Dashboard**
2. **Selecciona tu servicio de API**
3. **Haz clic en "Settings"**
4. **En "Build & Deploy":**
   - **Root Directory:** `source` (solo la palabra)
   - **Build Command:** `pip install -r requirements.txt` (SIN `cd source &&`)
   - **Start Command:** `gunicorn api_server:app --config gunicorn_config.py` (SIN `cd source &&`)
5. **Guarda los cambios**
6. **Render reiniciará automáticamente**

---

## Verificación

Después de corregir, los logs deberían mostrar:

```
==> Running build command 'pip install -r requirements.txt'...
==> Installing dependencies...
==> Build succeeded ✅
```

---

## Si el Error Persiste

1. **Verifica que `source/` esté en GitHub**
2. **Elimina el servicio en Render**
3. **Crea un nuevo servicio desde cero**
4. **Configura Root Directory = `source`**
5. **Configura Build Command SIN `cd source &&`**

