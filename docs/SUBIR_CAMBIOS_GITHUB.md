# 📤 Subir Cambios a GitHub - Guía Rápida

## 🚀 Opción 1: GitHub Desktop (Más Fácil)

### Paso 1: Abrir GitHub Desktop
1. Presiona **Windows** y escribe `GitHub Desktop`
2. Abre la aplicación

### Paso 2: Ver tus Cambios
1. GitHub Desktop mostrará todos los archivos modificados
2. Verás una lista de archivos con cambios en la parte inferior

### Paso 3: Hacer Commit
1. **Arriba a la izquierda**, en el campo **"Summary"**, escribe:
   ```
   Fix: Corregir creación de tokens y endpoints de API
   ```
2. **Opcional**: Agrega una descripción más detallada en "Description"
3. **Marca todos los archivos** que quieres subir (o déjalos todos marcados)
4. Click en **"Commit to main"** (botón azul abajo a la izquierda)

### Paso 4: Subir a GitHub
1. Después del commit, verás un botón **"Push origin"** arriba
2. Click en **"Push origin"**
3. Espera unos segundos
4. ¡Listo! Tus cambios están en GitHub

---

## 💻 Opción 2: Línea de Comandos (Git)

### Paso 1: Abrir Terminal
1. Abre **PowerShell** o **CMD**
2. Navega a tu proyecto:
   ```bash
   cd "C:\Users\robin\Desktop\Tareas\Aplicación de SS"
   ```

### Paso 2: Ver Cambios
```bash
git status
```

### Paso 3: Agregar Archivos
```bash
git add .
```
(O para agregar archivos específicos: `git add web_app/app.py web_app/static/js/panel.js`)

### Paso 4: Hacer Commit
```bash
git commit -m "Fix: Corregir creación de tokens y endpoints de API"
```

### Paso 5: Subir a GitHub
```bash
git push origin main
```

---

## ✅ Verificar que Funcionó

1. Ve a: https://github.com/aspersink-svg/aspersprojectsSS
2. Deberías ver tus cambios más recientes
3. Los archivos modificados deberían aparecer con la fecha/hora actual

---

## 🆘 Problemas Comunes

### "No changes to commit"
**Solución:** Todos los archivos ya están commiteados. Solo haz click en **"Push origin"**.

### "Authentication failed"
**Solución:** 
- En GitHub Desktop: **File** → **Options** → **Accounts** → Vuelve a iniciar sesión
- En línea de comandos: Necesitas configurar tu token de acceso personal

### "Repository not found"
**Solución:** Verifica que el repositorio `aspersprojectsSS` exista en GitHub.

---

## 💡 Tips

- **Haz commits frecuentes** - Es mejor hacer muchos commits pequeños que uno grande
- **Escribe mensajes claros** - Describe qué cambiaste y por qué
- **Revisa los cambios** antes de hacer commit - GitHub Desktop te muestra qué cambió en cada archivo

---

**¿Prefieres usar GitHub Desktop o línea de comandos?** GitHub Desktop es más fácil y visual.

