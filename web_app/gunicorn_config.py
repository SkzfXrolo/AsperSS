"""
Configuración de Gunicorn para Render
"""
import multiprocessing
import os

# gthread: 1 proceso con N threads.
# - Evita el deadlock de self-calls (threads concurrentes vs fork)
# - El bot de Discord y los request-handlers comparten el mismo proceso
#   → notify_new_scan / notify_verdict_change pueden usar el bot_loop directamente
workers = 1
threads = 4
worker_class = "gthread"

# Timeout más alto para sobrevivir el cold start de Render (spin-up desde sleep)
timeout = 120
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
max_requests = 1000
max_requests_jitter = 50

