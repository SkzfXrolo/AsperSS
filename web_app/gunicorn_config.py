"""
Configuración de Gunicorn para Render

Notas (2026-05) — outage reciente:
  El servicio quedó "Live" en Render pero ninguna request respondía. Causa
  más probable: 1 solo worker bloqueado en una request larga (o deadlock
  entre el event loop de Discord y los threads de gunicorn) — sin worker
  disponible, ni siquiera /healthz contesta. Cambios:
    - 2 workers en lugar de 1: si uno se cuelga, el otro sigue atendiendo
      mientras gunicorn lo recicla. Render Free Web (512 MB) suele aguantar
      bien 2 workers gthread con preload_app=False (cada uno carga sklearn,
      etc. en lazy import).
    - graceful_timeout: gunicorn espera N segundos a que un worker termine
      una request en curso antes de matarlo a SIGKILL al hacer reload o
      cuando excede `timeout`. Antes era el default 30 → si el worker está
      colgado, se queda zombie sin liberar el puerto.
    - threads bajados de 4 → 2 por worker para que dos requests no monopolicen
      el worker entero (con 2 workers x 2 threads = 4 concurrent requests).
    - timeout 60 (en vez de 120) para detectar bloqueos antes y reciclar.
"""
import multiprocessing
import os

# gthread: cada worker es un proceso con N threads.
# El bot de Discord arranca dentro de UNO de los workers (el primero que
# atienda); las notificaciones cross-worker viajan por DB / webhook directo.
workers = 2
threads = 2
worker_class = "gthread"

# Timeout más bajo para detectar y matar requests colgadas antes de que el
# servicio entero se vuelva inalcanzable (antes 120s).
timeout = 60
graceful_timeout = 30
keepalive = 5

# Bind - Render asigna el puerto automáticamente en la variable PORT
port = os.environ.get('PORT', '10000')
bind = f"0.0.0.0:{port}"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Forzar stdout sin buffer (necesario para que print() aparezca en Render logs inmediatamente)
import os as _os
_os.environ.setdefault('PYTHONUNBUFFERED', '1')

# NO preload con gthread — el bot se inicia dentro del worker, no en el master
preload_app = False

# Max requests (reinicia workers después de N requests para evitar memory leaks)
# Cada worker se recicla por separado; con 2 workers el reciclo es escalonado.
max_requests = 800
max_requests_jitter = 100

