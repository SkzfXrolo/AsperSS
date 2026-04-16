# 🌐 Guía para Hostear la Aplicación Web Gratis desde tu PC

Esta guía te muestra cómo exponer tu aplicación web al mundo sin pagar nada, usando tu propia PC.

## 🚀 Opción 1: ngrok (MÁS FÁCIL - Recomendado)

### Ventajas:
- ✅ Muy fácil de usar
- ✅ HTTPS automático
- ✅ URL pública inmediata
- ✅ Gratis con algunas limitaciones

### Pasos:

1. **Descargar ngrok:**
   - Ve a https://ngrok.com/download
   - Descarga para Windows
   - Extrae el archivo `ngrok.exe` en una carpeta (ej: `C:\ngrok\`)

2. **Crear cuenta gratuita:**
   - Ve a https://dashboard.ngrok.com/signup
   - Crea una cuenta gratuita
   - Copia tu "Authtoken" del dashboard

3. **Configurar ngrok:**
   ```bash
   # En PowerShell o CMD
   cd C:\ngrok
   .\ngrok.exe config add-authtoken TU_AUTHTOKEN_AQUI
   ```

4. **Iniciar tu aplicación Flask:**
   ```bash
   cd C:\Users\robin\Desktop\Tareas\Aplicación de SS\web_app
   python app.py
   ```
   (Tu app debería estar corriendo en `http://localhost:8080`)

5. **Crear túnel con ngrok:**
   ```bash
   # En otra terminal
   cd C:\ngrok
   .\ngrok.exe http 8080
   ```

6. **¡Listo!** ngrok te dará una URL pública como:
   ```
   https://abc123.ngrok-free.app
   ```
   Esta URL es accesible desde cualquier parte del mundo.

### Limitaciones de la versión gratuita:
- La URL cambia cada vez que reinicias ngrok (a menos que uses un dominio personalizado)
- Límite de conexiones simultáneas
- Límite de ancho de banda

---

## 🔒 Opción 2: Cloudflare Tunnel (cloudflared) - RECOMENDADO PARA PRODUCCIÓN

### Ventajas:
- ✅ Completamente gratis
- ✅ Sin límites de ancho de banda
- ✅ HTTPS automático
- ✅ Puedes usar tu propio dominio
- ✅ Más estable que ngrok

### Pasos:

1. **Descargar cloudflared:**
   - Ve a https://github.com/cloudflare/cloudflared/releases
   - Descarga `cloudflared-windows-amd64.exe`
   - Renómbralo a `cloudflared.exe` y guárdalo en una carpeta (ej: `C:\cloudflared\`)

2. **Crear túnel rápido (sin cuenta - RECOMENDADO si no tienes dominio):**
   ```bash
   cd C:\cloudflared
   .\cloudflared.exe tunnel --url http://localhost:8080
   ```
   Esto te dará una URL pública inmediatamente (tipo: `https://abc123.trycloudflare.com`).
   
   **⚠️ IMPORTANTE:** Si no tienes dominio en Cloudflare, usa esta opción. Es la más simple.

3. **O crear túnel permanente (con cuenta de Cloudflare):**
   
   **Si NO tienes dominio en Cloudflare:**
   - Cierra la ventana de autorización que se abrió
   - Usa el túnel rápido de arriba (Opción 2) - es más simple
   
   **Si SÍ tienes dominio en Cloudflare:**
   ```bash
   # Login (selecciona tu dominio cuando aparezca)
   .\cloudflared.exe tunnel login
   
   # Crear túnel con nombre
   .\cloudflared.exe tunnel create aspers-app
   
   # Configurar túnel con tu dominio
   .\cloudflared.exe tunnel route dns aspers-app panel.tu-dominio.com
   
   # Iniciar túnel
   .\cloudflared.exe tunnel run aspers-app
   ```
   
   **Nota:** Si al hacer login no ves ningún dominio, significa que no tienes dominios en Cloudflare. En ese caso, usa la Opción 2 (túnel rápido).

---

## 🔧 Opción 3: localhost.run (SSH Túnel)

### Ventajas:
- ✅ No requiere instalación adicional
- ✅ Funciona con SSH (si tienes SSH instalado)

### Pasos:

1. **Si tienes SSH instalado (Git Bash incluye SSH):**
   ```bash
   ssh -R 80:localhost:8080 ssh.localhost.run
   ```

2. **O usar cliente SSH de Windows:**
   - Instala OpenSSH desde Windows Features
   - Ejecuta el comando anterior

---

## 📝 Opción 4: Script Automático para ngrok

He creado un script que automatiza el proceso:

### Crear archivo `INICIAR_CON_NGROK.bat`:

```batch
@echo off
echo ========================================
echo   ASPERS Projects - Iniciar con ngrok
echo ========================================
echo.

REM Cambiar esta ruta a donde tengas ngrok.exe
set NGROK_PATH=C:\ngrok\ngrok.exe

REM Cambiar esta ruta a donde está tu aplicación
set APP_PATH=%~dp0

echo [1/3] Iniciando aplicación Flask...
start "ASPERS Flask App" cmd /k "cd /d %APP_PATH% && python app.py"

timeout /t 3 /nobreak >nul

echo [2/3] Esperando que la aplicación inicie...
timeout /t 5 /nobreak >nul

echo [3/3] Iniciando túnel ngrok...
start "ngrok Tunnel" cmd /k "%NGROK_PATH% http 8080"

echo.
echo ========================================
echo   ¡Aplicación iniciada!
echo ========================================
echo.
echo La aplicación está corriendo en:
echo   - Local: http://localhost:8080
echo   - Público: Revisa la ventana de ngrok para la URL
echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause >nul
```

---

## 🔐 Opción 5: Port Forwarding (Avanzado)

Si tienes acceso a tu router y quieres una solución más permanente:

### Pasos:

1. **Configurar IP estática en tu PC:**
   - Configuración de Red → Cambiar opciones del adaptador
   - Propiedades de tu conexión → IPv4
   - Configurar IP estática (ej: 192.168.1.100)

2. **Abrir puerto en el router:**
   - Accede a tu router (normalmente 192.168.1.1 o 192.168.0.1)
   - Ve a "Port Forwarding" o "Virtual Server"
   - Redirige puerto externo (ej: 8080) a IP interna:8080

3. **Obtener tu IP pública:**
   - Ve a https://whatismyipaddress.com
   - Tu URL pública será: `http://TU_IP_PUBLICA:8080`

### ⚠️ ADVERTENCIAS DE SEGURIDAD:
- Tu PC estará expuesto directamente a internet
- Necesitas firewall configurado correctamente
- Considera usar HTTPS con certificado SSL
- No recomendado para producción sin medidas de seguridad adicionales

---

## 🎯 Recomendación Final

**Para desarrollo/pruebas:** Usa **ngrok** (Opción 1) - Es la más fácil y rápida.

**Para uso más permanente:** Usa **Cloudflare Tunnel** (Opción 2) - Es gratis, estable y sin límites.

---

## 📋 Checklist de Seguridad

Antes de exponer tu aplicación:

- [ ] Cambiar `SECRET_KEY` en `app.py` por una clave segura
- [ ] Cambiar `API_SECRET_KEY` si es necesario
- [ ] Revisar que `login_required` esté en todas las rutas sensibles
- [ ] Considerar agregar rate limiting
- [ ] Revisar logs de acceso regularmente
- [ ] Usar HTTPS (ngrok y Cloudflare lo proporcionan automáticamente)

---

## 🆘 Solución de Problemas

### Error: "Address already in use"
- Alguien más está usando el puerto 8080
- Cambia el puerto en `app.py`: `app.run(host='0.0.0.0', port=8081)`
- Actualiza ngrok: `ngrok http 8081`

### Error: "Connection refused"
- Asegúrate de que Flask esté corriendo en `localhost:8080`
- Verifica que no haya firewall bloqueando

### La URL de ngrok cambia cada vez
- Esto es normal en la versión gratuita
- Considera usar Cloudflare Tunnel para URLs más estables

---

## 📞 Soporte

Si tienes problemas, verifica:
1. Que Flask esté corriendo correctamente
2. Que el puerto sea el correcto (8080 por defecto)
3. Que no haya firewall bloqueando
4. Que ngrok/cloudflared estén actualizados

