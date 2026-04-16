# 📤 Añadir Carpetas build y dist Manualmente

## Método 1: GitHub Desktop (Más Fácil)

### Paso 1: Abrir GitHub Desktop

1. **Abre GitHub Desktop**
2. **Asegúrate de estar en el repositorio correcto** (`aspersprojectsSS`)

### Paso 2: Forzar la Adición de Carpetas

1. **En la pestaña "Changes"**, busca en la parte inferior izquierda

2. **Si no ves las carpetas**, haz clic en el botón **"..."** (tres puntos) en la esquina superior derecha

3. **Selecciona "Show in Explorer"** o **"Reveal in Finder"**

4. **Navega manualmente a:**
   - `source/build/`
   - `source/dist/`

5. **En GitHub Desktop, en la pestaña "Changes":**
   - Si ves archivos sin marcar, **marca la casilla** junto a cada archivo
   - Si no ves nada, continúa con el Método 2

### Paso 3: Usar el Terminal Integrado

1. **En GitHub Desktop**, ve a **"Repository" → "Open in Command Prompt"** (o Terminal)

2. **Ejecuta estos comandos uno por uno:**

```bash
git add -f source/build/
git add -f source/build/*
git add -f source/build/**/*

git add -f source/dist/
git add -f source/dist/*
git add -f source/dist/**/*
```

3. **Verifica que se agregaron:**
```bash
git status
```

4. **Deberías ver archivos en verde** como:
```
new file:   source/build/.gitkeep
new file:   source/build/MinecraftSSTool/Analysis-00.toc
new file:   source/dist/.gitkeep
new file:   source/dist/MinecraftSSTool.exe
...
```

5. **Vuelve a GitHub Desktop** - ahora deberías ver todos los archivos en "Changes"

6. **Escribe un mensaje de commit:** "Agregar carpetas build y dist"

7. **Haz clic en "Commit to main"**

8. **Haz clic en "Push origin"** para subir a GitHub

---

## Método 2: PowerShell/CMD Manual

### Paso 1: Abrir Terminal

1. **Abre PowerShell o CMD**
2. **Navega a la carpeta del proyecto:**
```bash
cd "C:\Users\robin\Desktop\Tareas\Aplicación de SS"
```

### Paso 2: Verificar que las Carpetas Existen

```bash
dir source\build
dir source\dist
```

Deberías ver los archivos dentro.

### Paso 3: Agregar las Carpetas a Git

**Ejecuta estos comandos uno por uno:**

```bash
# Agregar carpeta build completa
git add -f source/build/

# Agregar todos los archivos en build
git add -f source/build/*

# Agregar todos los subdirectorios y archivos
git add -f source/build/**/*

# Agregar carpeta dist completa
git add -f source/dist/

# Agregar todos los archivos en dist
git add -f source/dist/*

# Agregar todos los subdirectorios y archivos
git add -f source/dist/**/*
```

### Paso 4: Verificar

```bash
git status
```

Deberías ver muchos archivos nuevos listados.

### Paso 5: Commit y Push

```bash
git commit -m "Agregar carpetas build y dist con todos los archivos"
git push
```

---

## Método 3: Agregar Archivos Específicos

Si los métodos anteriores no funcionan, agrega archivos específicos:

### Para el .exe (MUY IMPORTANTE):

```bash
git add -f source/dist/MinecraftSSTool.exe
```

### Para otros archivos importantes:

```bash
# Archivos de build
git add -f source/build/MinecraftSSTool/
git add -f source/build/MinecraftSSTool/*

# Archivos de dist
git add -f source/dist/models/
git add -f source/dist/models/*
```

### Luego verifica y commit:

```bash
git status
git commit -m "Agregar ejecutable y archivos de compilación"
git push
```

---

## Método 4: Arrastrar y Soltar en GitHub Web

1. **Ve a tu repositorio en GitHub:**
   ```
   https://github.com/aspersink-svg/aspersprojectsSS
   ```

2. **Navega a la carpeta `source/`**

3. **Haz clic en "Add file" → "Upload files"**

4. **Arrastra las carpetas `build/` y `dist/`** completas

5. **Haz clic en "Commit changes"**

⚠️ **Nota:** Este método puede ser lento si hay muchos archivos o archivos grandes.

---

## Verificación Final

Después de subir, verifica en GitHub:

1. **Ve a:** `https://github.com/aspersink-svg/aspersprojectsSS/tree/main/source`

2. **Deberías ver:**
   - ✅ Carpeta `build/` (con contenido)
   - ✅ Carpeta `dist/` (con `MinecraftSSTool.exe`)

3. **Haz clic en cada carpeta** para verificar que los archivos están ahí

---

## Si Nada Funciona

### Verificar .gitignore

Abre el archivo `.gitignore` y asegúrate de que tenga estas líneas:

```
build/
!source/build/
!source/build/**
dist/
!source/dist/
!source/dist/**
```

### Limpiar Cache de Git

```bash
git rm -r --cached source/build/
git rm -r --cached source/dist/
git add -f source/build/
git add -f source/dist/
git commit -m "Forzar adición de carpetas build y dist"
git push
```

---

## Problemas Comunes

### "fatal: pathspec 'source/build/' did not match any files"

**Solución:** La carpeta no existe o está vacía. Compila primero:
```
BAT\01-Compilar\COMPILAR_FINAL.bat
```

### "The file will have its original line endings"

**Solución:** Esto es normal, solo un aviso. Continúa con el commit.

### "File is too large"

**Solución:** El .exe es muy grande (>100MB). GitHub no permite archivos tan grandes. Considera usar Git LFS o comprimir el archivo.

---

## ¿Cuál Método Usar?

- **Método 1 (GitHub Desktop):** Si prefieres interfaz gráfica
- **Método 2 (PowerShell):** Si te sientes cómodo con comandos
- **Método 3 (Archivos específicos):** Si solo necesitas el .exe
- **Método 4 (GitHub Web):** Si los otros no funcionan

