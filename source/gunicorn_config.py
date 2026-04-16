"""
Configuración de Gunicorn para Render - API Server
"""
import multiprocessing
import os

# Número de workers (para SQLite, usar 1 es más seguro)
workers = 1  # SQLite no maneja bien múltiples workers simultáneos

# Timeout (aumentado para operaciones de base de datos)
timeout = 180  # 3 minutos

# Bind - Render asigna el puerto automáticamente en la variable PORT
port = os.environ.get('PORT', '5000')
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

