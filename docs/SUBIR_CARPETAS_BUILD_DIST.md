# 📤 Subir Carpetas build y dist a GitHub

## Problema

Las carpetas `source/build/` y `source/dist/` no aparecen en GitHub, aunque existen localmente.

## Causa

Git no rastrea carpetas vacías, y algunos archivos dentro pueden estar siendo ignorados por el `.gitignore`.

## Solución

### Opción 1: Script Automático (Recomendado)

1. **Ejecuta el script:**
   ```
   SUBIR_CARPETAS_BUILD_DIST.bat
   ```

2. **Abre GitHub Desktop**

3. **Verás todos los archivos de `source/build/` y `source/dist/` como nuevos**

4. **Haz commit** con el mensaje: "Agregar carpetas build y dist"

5. **Haz push** para subirlos a GitHub

### Opción 2: Manualmente con Git

1. **Abre PowerShell o CMD en la carpeta del proyecto**

2. **Agrega las carpetas forzadamente:**
   ```bash
   git add -f source/build/
   git add -f source/build/*
   git add -f source/build/**/*
   
   git add -f source/dist/
   git add -f source/dist/*
   git add -f source/dist/**/*
   ```

3. **Verifica qué se agregó:**
   ```bash
   git status
   ```

4. **Haz commit:**
   ```bash
   git commit -m "Agregar carpetas build y dist"
   ```

5. **Haz push:**
   ```bash
   git push
   ```

### Opción 3: Usando GitHub Desktop

1. **Abre GitHub Desktop**

2. **En la pestaña "Changes"**, busca archivos en:
   - `source/build/`
   - `source/dist/`

3. **Si no aparecen**, haz clic derecho en la carpeta y selecciona "Add to Git"

4. **Haz commit y push**

## Verificación

Para verificar que las carpetas están en GitHub:

1. **Ve a tu repositorio:**
   ```
   https://github.com/aspersink-svg/aspersprojectsSS
   ```

2. **Navega a:**
   - `source/build/` - Deberías ver la carpeta `MinecraftSSTool/` y sus archivos
   - `source/dist/` - Deberías ver `MinecraftSSTool.exe` y otros archivos

## Archivos Importantes que Deben Subirse

### En `source/build/`:
- `MinecraftSSTool/` (carpeta completa)
- Todos los archivos `.toc`, `.pkg`, `.pyz`, etc.

### En `source/dist/`:
- `MinecraftSSTool.exe` ⚠️ **MUY IMPORTANTE**
- `models/ai_model_latest.json`
- `scanner_db.sqlite` (opcional, se puede regenerar)

## Notas Importantes

- ⚠️ **El .exe puede ser grande (50-100MB)** - GitHub permite hasta 100MB por archivo
- ⚠️ **Si el .exe es muy grande**, GitHub puede rechazarlo
- ⚠️ **Las carpetas vacías no se suben** - Por eso creamos archivos `.gitkeep`
- ⚠️ **Cada vez que recompiles**, debes volver a subir los cambios

## Si el Problema Persiste

1. **Verifica el `.gitignore`:**
   - Debe tener `!source/build/**` y `!source/dist/**`
   - Debe tener `!source/dist/*.exe` y `!source/build/*.exe`

2. **Fuerza la adición de archivos específicos:**
   ```bash
   git add -f source/dist/MinecraftSSTool.exe
   git add -f source/build/MinecraftSSTool/
   ```

3. **Verifica que los archivos existan localmente:**
   - `source/dist/MinecraftSSTool.exe` debe existir
   - `source/build/MinecraftSSTool/` debe existir

4. **Si las carpetas están vacías**, compila primero:
   ```
   BAT\01-Compilar\COMPILAR_FINAL.bat
   ```

