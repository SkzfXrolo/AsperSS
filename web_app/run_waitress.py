"""Servidor de produccion local (Waitress) para exponer el panel via cloudflared.

No usar `python app.py` (servidor dev de Flask) para exponer el panel a
internet. Este script sirve la misma app Flask con Waitress, apto para
recibir trafico externo. Socket.IO cae a long-polling (Waitress no soporta
upgrade a WebSocket nativo), pero el chat/tiempo real sigue funcionando.
"""
import os

from waitress import serve

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    threads = int(os.environ.get("WAITRESS_THREADS", "8"))
    serve(app, host="127.0.0.1", port=port, threads=threads)
