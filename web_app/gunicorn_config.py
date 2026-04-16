"""
Configuración de Gunicorn para Render
"""
import multiprocessing
import os

# Workers: mínimo 2 para evitar deadlock cuando la app se llama a sí misma via HTTP
# Con 1 solo worker sync, Request A espera a Request B pero B no puede ejecutarse → congelado
workers = 2

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

# Worker class
worker_class = "sync"

# Preload app (carga la app antes de fork)
preload_app = True

# Max requests (reinicia workers después de N requests para evitar memory leaks)
max_requests = 1000
max_requests_jitter = 50

