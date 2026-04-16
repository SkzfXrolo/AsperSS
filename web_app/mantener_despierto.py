"""
Script para mantener el servidor de Render despierto
Ejecuta este script si tienes una PC siempre encendida
"""
import requests
import time
from datetime import datetime

# Configuración
URL = "https://aspersprojectsss.onrender.com/health"  # Cambia por tu URL
INTERVAL = 10 * 60  # 10 minutos en segundos

print("=" * 60)
print("🔄 Keep-Alive para Render")
print("=" * 60)
print(f"📍 URL: {URL}")
print(f"⏰ Intervalo: {INTERVAL/60} minutos")
print(f"🛑 Presiona Ctrl+C para detener")
print("=" * 60)
print()

try:
    while True:
        try:
            start_time = time.time()
            response = requests.get(URL, timeout=30)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                print(f"✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Servidor activo (respondió en {elapsed:.2f}s)")
            else:
                print(f"⚠️  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Servidor respondió con código {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"⏱️  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Timeout - El servidor puede estar despertando...")
        except requests.exceptions.ConnectionError:
            print(f"❌ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error de conexión")
        except Exception as e:
            print(f"❌ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: {e}")
        
        # Esperar antes del siguiente ping
        print(f"💤 Esperando {INTERVAL/60} minutos hasta el siguiente ping...")
        time.sleep(INTERVAL)
        
except KeyboardInterrupt:
    print("\n\n🛑 Keep-alive detenido por el usuario")
    print("👋 ¡Hasta luego!")

