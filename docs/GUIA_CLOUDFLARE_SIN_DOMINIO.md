# 🌐 Guía: Cloudflare Tunnel SIN Dominio Propio

Si no tienes un dominio propio en Cloudflare, puedes usar Cloudflare Tunnel de forma gratuita con una URL proporcionada por Cloudflare.

## ✅ Opción 1: Túnel Rápido (SIN cuenta - Más fácil)

**Esta es la opción más simple si no tienes dominio:**

```bash
cd C:\cloudflared
.\cloudflared.exe tunnel --url http://localhost:8080
```

**Ventajas:**
- ✅ No requiere cuenta de Cloudflare
- ✅ Funciona inmediatamente
- ✅ Completamente gratis
- ✅ HTTPS automático

**Desventajas:**
- ⚠️ La URL cambia cada vez que reinicias el túnel
- ⚠️ URL tipo: `https://abc123-def456.trycloudflare.com`

---

## ✅ Opción 2: Túnel Permanente SIN Dominio (Con cuenta)

Si quieres una URL más estable pero SIN dominio propio:

### Paso 1: Cerrar la ventana de autorización

En la ventana que se abrió, simplemente:
- **Cierra la ventana** o haz clic en "Cancel"
- No necesitas seleccionar ningún dominio

### Paso 2: Crear túnel sin dominio

```bash
# Crear túnel (sin necesidad de dominio)
.\cloudflared.exe tunnel create aspers-app
```

Esto creará un túnel con una URL tipo: `aspers-app.trycloudflare.com`

### Paso 3: Configurar el túnel

Necesitas crear un archivo de configuración. Crea un archivo llamado `config.yml` en la misma carpeta donde está `cloudflared.exe`:

```yaml
tunnel: aspers-app
credentials-file: C:\cloudflared\<TU_TUNNEL_ID>.json

ingress:
  - hostname: aspers-app.trycloudflare.com
    service: http://localhost:8080
  - service: http_status:404
```

**Nota:** Reemplaza `<TU_TUNNEL_ID>` con el ID que te dio Cloudflare cuando creaste el túnel.

### Paso 4: Iniciar el túnel

```bash
.\cloudflared.exe tunnel run aspers-app
```

---

## ✅ Opción 3: Túnel Permanente CON Dominio (Si tienes dominio)

Si tienes un dominio y quieres usarlo:

### Paso 1: Agregar dominio a Cloudflare

1. Ve a https://dash.cloudflare.com
2. Haz clic en "Add a Site"
3. Ingresa tu dominio (ej: `tudominio.com`)
4. Sigue las instrucciones para cambiar los nameservers

### Paso 2: Una vez agregado el dominio

Vuelve a ejecutar:
```bash
.\cloudflared.exe tunnel login
```

Ahora SÍ verás tu dominio en la lista y podrás seleccionarlo.

### Paso 3: Crear y configurar túnel

```bash
# Crear túnel
.\cloudflared.exe tunnel create aspers-app

# Configurar con tu dominio
.\cloudflared.exe tunnel route dns aspers-app panel.tudominio.com

# Iniciar túnel
.\cloudflared.exe tunnel run aspers-app
```

---

## 🎯 Recomendación para tu caso

**Como no tienes dominio configurado, te recomiendo:**

### Usar el Túnel Rápido (Opción 1)

Es la más simple y funciona perfectamente:

```bash
cd C:\cloudflared
.\cloudflared.exe tunnel --url http://localhost:8080
```

**Ventajas:**
- ✅ Funciona inmediatamente
- ✅ No necesitas cuenta
- ✅ No necesitas dominio
- ✅ Completamente gratis
- ✅ HTTPS automático

**Solo recuerda:**
- La URL cambiará cada vez que reinicies el túnel
- Pero puedes copiar la nueva URL y compartirla

---

## 📝 Script Automático para Túnel Rápido

Puedo crear un script `.bat` que inicie tu aplicación Flask y el túnel automáticamente. ¿Te interesa?

---

## ❓ Preguntas Frecuentes

**P: ¿Necesito dominio para usar Cloudflare Tunnel?**
R: No, puedes usar el túnel rápido sin dominio ni cuenta.

**P: ¿La URL cambiará siempre?**
R: Solo con el túnel rápido. Si quieres URL fija, necesitas cuenta de Cloudflare (aunque sea gratis).

**P: ¿Es seguro sin dominio?**
R: Sí, Cloudflare proporciona HTTPS automático incluso sin dominio propio.

**P: ¿Puedo usar mi dominio después?**
R: Sí, cuando agregues tu dominio a Cloudflare, puedes migrar el túnel.

