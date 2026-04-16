# ⚡ Mantener el Servidor Despierto en Render (Plan Gratuito)

## 🔍 Problema

En el plan gratuito de Render, el servidor se "duerme" después de **15 minutos de inactividad** y tarda **~30 segundos** en despertarse. Esto causa errores **502 Bad Gateway** cuando alguien intenta acceder mientras está durmiendo.

## ✅ Soluciones

### Solución 1: UptimeRobot (Recomendado - Gratis)

**UptimeRobot** es un servicio gratuito que hace ping a tu servidor cada 5 minutos para mantenerlo despierto.

#### Pasos:

1. **Crear cuenta en UptimeRobot**
   - Ve a: https://uptimerobot.com
   - Crea una cuenta gratuita (permite hasta 50 monitores)

2. **Agregar Monitor**
   - Click en **"Add New Monitor"**
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: ASPERS Web App (o el nombre que quieras)
   - **URL**: `https://aspersprojectsss.onrender.com/health`
   - **Monitoring Interval**: 5 minutes
   - **Alert Contacts**: (Opcional) Tu email para recibir alertas
   - Click **"Create Monitor"**

3. **¡Listo!**
   - UptimeRobot hará ping cada 5 minutos
   - Tu servidor nunca se dormirá

**Ventajas:**
- ✅ Completamente gratis
- ✅ Muy confiable
- ✅ No requiere código adicional
- ✅ Te avisa si el servidor está caído

---

### Solución 2: cron-job.org (Alternativa)

**cron-job.org** es otro servicio gratuito que puede hacer peticiones HTTP periódicas.

#### Pasos:

1. **Crear cuenta**
   - Ve a: https://cron-job.org
   - Crea una cuenta gratuita

2. **Crear Cron Job**
   - Click en **"Create cronjob"**
   - **Title**: Keep ASPERS Alive
   - **Address**: `https://aspersprojectsss.onrender.com/health`
   - **Schedule**: Cada 10 minutos (`*/10 * * * *`)
   - Click **"Create cronjob"**

3. **¡Listo!**
   - El cron job hará ping cada 10 minutos

---

### Solución 3: GitHub Actions (Si tienes el código en GitHub)

Puedes usar GitHub Actions para hacer ping automáticamente.

#### Crear archivo `.github/workflows/keep-alive.yml`:

```yaml
name: Keep Render Server Alive

on:
  schedule:
    # Ejecuta cada 10 minutos
    - cron: '*/10 * * * *'
  workflow_dispatch: # Permite ejecución manual

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping Render Server
        run: |
          curl -f https://aspersprojectsss.onrender.com/health || exit 1
```

**Pasos:**
1. Crea la carpeta `.github/workflows/` en tu repositorio
2. Crea el archivo `keep-alive.yml` con el contenido de arriba
3. Reemplaza `aspersprojectsss.onrender.com` con tu URL
4. Sube a GitHub
5. GitHub Actions ejecutará automáticamente cada 10 minutos

---

### Solución 4: Python Script Local (Si tienes una PC siempre encendida)

Si tienes una computadora que siempre está encendida, puedes ejecutar un script simple.

#### Crear `mantener_despierto.py`:

```python
import requests
import time
from datetime import datetime

URL = "https://aspersprojectsss.onrender.com/health"
INTERVAL = 10 * 60  # 10 minutos en segundos

print(f"🔄 Iniciando keep-alive para {URL}")
print(f"⏰ Intervalo: {INTERVAL/60} minutos")

while True:
    try:
        response = requests.get(URL, timeout=30)
        if response.status_code == 200:
            print(f"✅ [{datetime.now()}] Servidor activo")
        else:
            print(f"⚠️  [{datetime.now()}] Servidor respondió con código {response.status_code}")
    except Exception as e:
        print(f"❌ [{datetime.now()}] Error: {e}")
    
    time.sleep(INTERVAL)
```

**Ejecutar:**
```bash
python mantener_despierto.py
```

**Nota:** Esto requiere que tu PC esté siempre encendida.

---

## 🎯 Recomendación

**Usa UptimeRobot (Solución 1)** porque:
- ✅ Es la más fácil de configurar
- ✅ No requiere código
- ✅ Es muy confiable
- ✅ Te avisa si hay problemas
- ✅ Completamente gratis

---

## 📋 Configuración del Health Check

Asegúrate de que tu aplicación tenga el endpoint `/health`:

```python
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), 200
```

Este endpoint debe:
- ✅ Responder rápidamente (< 1 segundo)
- ✅ No requerir autenticación
- ✅ No hacer operaciones pesadas
- ✅ Devolver código 200

---

## ⚠️ Notas Importantes

1. **No abuses del ping**: Hacer ping cada 1-2 minutos puede ser considerado abuso. Usa intervalos de 5-10 minutos.

2. **El servidor puede tardar en despertar**: Aunque hagas ping regularmente, si alguien accede justo cuando se está despertando, puede ver un 502. Esto es normal y se resuelve en ~30 segundos.

3. **Plan gratuito tiene limitaciones**: El plan gratuito de Render está diseñado para desarrollo/testing. Para producción, considera el plan de pago.

---

## 🔧 Verificar que Funciona

1. **Espera 20 minutos** sin usar el servidor
2. **Haz ping manualmente**:
   ```bash
   curl https://aspersprojectsss.onrender.com/health
   ```
3. **Si responde rápido** (< 1 segundo), el keep-alive está funcionando
4. **Si tarda ~30 segundos**, el servidor se durmió y el keep-alive no está funcionando

---

## 📞 Alternativas si Nada Funciona

Si ninguna solución funciona o necesitas más confiabilidad:

1. **Upgrade a plan de pago** de Render (desde $7/mes)
2. **Usar otro servicio** como Railway, Fly.io, o Heroku
3. **Hostear en tu propia VPS** (DigitalOcean, Linode, etc.)

---

**¿Necesitas ayuda configurando alguna de estas soluciones?** Te guío paso a paso.

