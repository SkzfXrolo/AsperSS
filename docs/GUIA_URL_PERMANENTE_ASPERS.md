# 🌐 Configurar URL Permanente con "AspersProjects"

Esta guía te ayudará a crear una URL permanente que empiece con "AspersProjects" usando Cloudflare Tunnel.

## 🎯 Objetivo

Crear una URL tipo: `https://aspersprojects-xxxxx.trycloudflare.com` que sea **permanente** (no cambie cada vez).

---

## 📋 Pasos Detallados

### Paso 1: Descargar Cloudflared

1. Ve a: https://github.com/cloudflare/cloudflared/releases
2. Descarga: `cloudflared-windows-amd64.exe`
3. Renómbralo a: `cloudflared.exe`
4. Guárdalo en una carpeta (ej: `C:\cloudflared\`)

### Paso 2: Agregar al PATH (Opcional pero recomendado)

Para poder usar `cloudflared` desde cualquier lugar:

1. Busca "Variables de entorno" en Windows
2. Agrega la carpeta donde está `cloudflared.exe` al PATH
3. O simplemente coloca `cloudflared.exe` en `C:\Windows\System32\`

### Paso 3: Crear Túnel Permanente

Abre PowerShell o CMD y ejecuta:

```bash
# Crear túnel con nombre "aspersprojects"
cloudflared tunnel create aspersprojects
```

**Si te pide login:**
- Se abrirá una ventana del navegador
- **Cierra la ventana** (no necesitas seleccionar dominio)
- El túnel se creará igual

**Resultado esperado:**
```
✅ Tunnel aspersprojects created
   ID: abc123def456...
```

### Paso 4: Configurar el Túnel

Necesitas crear un archivo de configuración. Crea un archivo llamado `config.yml` en la carpeta donde está `cloudflared.exe`:

**Ubicación del archivo:**
- Si cloudflared está en `C:\cloudflared\`, crea `C:\cloudflared\config.yml`

**Contenido del archivo `config.yml`:**

```yaml
tunnel: aspersprojects
credentials-file: C:\Users\<TU_USUARIO>\.cloudflared\<TUNNEL_ID>.json

ingress:
  - hostname: aspersprojects-xxxxx.trycloudflare.com
    service: http://localhost:8080
  - service: http_status:404
```

**⚠️ IMPORTANTE - Reemplazar valores:**

1. `<TU_USUARIO>`: Tu nombre de usuario de Windows (ej: `robin`)
2. `<TUNNEL_ID>`: El ID que te dio cuando creaste el túnel (ej: `abc123def456...`)

**Cómo encontrar el Tunnel ID:**

Después de crear el túnel, Cloudflare te mostrará algo como:
```
✅ Tunnel aspersprojects created
   ID: abc123def456ghi789
```

Ese ID es lo que necesitas.

**Ubicación del archivo JSON:**
El archivo JSON se crea automáticamente en: `C:\Users\<TU_USUARIO>\.cloudflared\<TUNNEL_ID>.json`

### Paso 5: Iniciar el Túnel

```bash
cloudflared tunnel run aspersprojects
```

**Resultado esperado:**
```
✅ Tunnel aspersprojects started
   URL: https://aspersprojects-xxxxx.trycloudflare.com
```

**¡Esa URL será PERMANENTE!** 🎉

---

## 🚀 Script Automático (Más Fácil)

He creado un script que hace todo automáticamente:

**Archivo:** `CONFIGURAR_TUNEL_PERMANENTE.bat`

**Qué hace:**
1. ✅ Inicia tu aplicación Flask
2. ✅ Crea el túnel "aspersprojects" (si no existe)
3. ✅ Inicia el túnel permanente
4. ✅ Te muestra la URL permanente

**Cómo usar:**
1. Coloca `cloudflared.exe` en el PATH o actualiza `CLOUDFLARE_PATH` en el script
2. Ejecuta `CONFIGURAR_TUNEL_PERMANENTE.bat`
3. ¡Listo! Tendrás tu URL permanente

---

## 🔧 Configuración Avanzada (Opcional)

Si quieres tener más control sobre la URL, puedes usar un dominio gratuito:

### Opción A: Dominio Gratuito de Freenom

1. Ve a: https://www.freenom.com
2. Registra un dominio gratis (ej: `aspersprojects.tk`)
3. Agrégalo a Cloudflare
4. Configura el túnel con tu dominio

### Opción B: Subdominio en Cloudflare

Si tienes acceso a algún dominio en Cloudflare, puedes crear:
- `aspersprojects.tudominio.com`

---

## 📝 Notas Importantes

1. **URL Permanente:** La URL será permanente mientras uses el mismo túnel con el mismo nombre
2. **Reiniciar:** Si reinicias tu PC, solo ejecuta el script nuevamente y tendrás la misma URL
3. **Múltiples Túneles:** Puedes crear varios túneles con diferentes nombres
4. **HTTPS Automático:** Cloudflare proporciona HTTPS automático, sin configuración adicional

---

## ❓ Solución de Problemas

**Error: "Tunnel already exists"**
- El túnel ya existe, puedes continuar con `tunnel run`

**Error: "Credentials file not found"**
- Verifica la ruta del archivo JSON en `config.yml`
- El archivo debería estar en `C:\Users\<TU_USUARIO>\.cloudflared\`

**La URL sigue cambiando**
- Asegúrate de usar `tunnel run aspersprojects` y no `tunnel --url`
- Verifica que el archivo `config.yml` esté correcto

---

## 🎉 Resultado Final

Tendrás una URL permanente tipo:
```
https://aspersprojects-xxxxx.trycloudflare.com
```

Que será **siempre la misma** cada vez que inicies el túnel con el mismo nombre.

