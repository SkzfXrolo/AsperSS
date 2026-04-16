"""
Configuración de Gunicorn para Render
"""
import multiprocessing
import os

# Número de workers (procesos) - Optimizado para Render free tier
# Usar solo 1 worker para evitar problemas de memoria y mejorar tiempo de respuesta
workers = 1  # Render free tier funciona mejor con 1 worker

# Timeout (reducido para respuestas más rápidas)
timeout = 30  # 30 segundos es suficiente para la mayoría de requests
keepalive = 2  # Mantener conexiones vivas por menos tiempo

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

