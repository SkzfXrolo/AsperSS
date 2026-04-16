# 🆓 Usar Dominio Gratuito con Cloudflare Tunnel

## ✅ SÍ, puedes usar un dominio gratuito

Cloudflare Tunnel funciona perfectamente con dominios gratuitos. Solo necesitas agregar el dominio a Cloudflare.

---

## 🎯 Opción 1: Dominios Gratuitos Compatibles con Cloudflare

### Servicios que ofrecen dominios gratuitos:

1. **Freenom** (https://www.freenom.com)
   - Dominios: `.tk`, `.ml`, `.ga`, `.cf`, `.gq`
   - ✅ Compatible con Cloudflare
   - ⚠️ Requiere renovación anual (gratis)

2. **Dot TK** (https://www.dot.tk)
   - Dominio: `.tk`
   - ✅ Compatible con Cloudflare

3. **No-IP** (https://www.noip.com)
   - Subdominios gratuitos
   - ⚠️ Requiere confirmación mensual

### Recomendación: **Freenom** (más fácil y confiable)

---

## 📋 Pasos para Configurar Dominio Gratuito

### Paso 1: Obtener Dominio Gratuito

1. Ve a: https://www.freenom.com
2. Busca un dominio (ej: `aspersprojects.tk`)
3. Selecciona "Get it now!" → "Checkout"
4. Selecciona período: 12 meses (gratis)
5. Completa el registro (puedes usar email temporal)
6. Confirma el email

### Paso 2: Agregar Dominio a Cloudflare

1. Ve a: https://dash.cloudflare.com
2. Click en "Add a Site"
3. Ingresa tu dominio (ej: `aspersprojects.tk`)
4. Selecciona plan "Free"
5. Cloudflare te dará 2 nameservers:
   - `donovan.ns.cloudflare.com`
   - `summer.ns.cloudflare.com`

### Paso 3: Configurar Nameservers en Freenom

1. Ve a: https://my.freenom.com
2. Login con tu cuenta
3. Ve a "Services" → "My Domains"
4. Click en "Manage Domain" de tu dominio
5. Ve a "Management Tools" → "Nameservers"
6. Selecciona "Use custom nameservers"
7. Agrega los 2 nameservers de Cloudflare:
   - `donovan.ns.cloudflare.com`
   - `summer.ns.cloudflare.com`
8. Guarda los cambios

### Paso 4: Esperar Activación

- ⏱️ Tiempo: 5 minutos a 24 horas (normalmente menos de 1 hora)
- Cloudflare te enviará un email cuando esté activo
- Puedes verificar en el dashboard de Cloudflare

### Paso 5: Configurar Cloudflare Tunnel con tu Dominio

Una vez activo, ejecuta:

```bash
CONFIGURAR_TUNEL_CON_DOMINIO.bat
```

O manualmente:

```bash
# 1. Crear túnel
C:\cloudflared\cloudflared.exe tunnel create aspersprojects

# 2. Configurar ruta DNS
C:\cloudflared\cloudflared.exe tunnel route dns aspersprojects aspersprojects.tk

# 3. Iniciar túnel
C:\cloudflared\cloudflared.exe tunnel run aspersprojects
```

---

## 🎯 Opción 2: Usar Subdominio Gratuito (Más Rápido)

Si no quieres esperar, puedes usar un subdominio de Cloudflare:

### Con Cloudflare Tunnel:

```bash
# El túnel crea automáticamente:
# https://aspersprojects-xxxxx.trycloudflare.com
```

Esto funciona inmediatamente sin configurar nada.

---

## 📝 Script Automático para Dominio Propio

Voy a crear un script que:
1. Verifica si tienes dominio en Cloudflare
2. Configura el túnel automáticamente
3. Crea la ruta DNS

---

## ⚠️ Consideraciones

### Dominios Gratuitos:
- ✅ Funcionan perfectamente con Cloudflare Tunnel
- ⚠️ Algunos requieren renovación periódica
- ⚠️ Pueden tener restricciones menores

### Recomendación:
- **Para empezar rápido**: Usa `trycloudflare.com` (inmediato)
- **Para producción**: Obtén dominio gratuito y configúralo

---

## 🚀 ¿Quieres que cree el script automático?

Puedo crear un script que:
- Detecta si tienes dominio en Cloudflare
- Configura el túnel automáticamente
- Crea la ruta DNS

¿Lo creo?

