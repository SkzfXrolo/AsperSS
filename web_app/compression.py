"""Compresión gzip + caché HTTP de estáticos, sin dependencias extra.

- Respuestas buffered (JSON, HTML, CSS, JS, SVG) >= 1 KB se comprimen si el
  cliente envía ``Accept-Encoding: gzip``.
- Los estáticos (``send_file`` con direct_passthrough) se comprimen una sola
  vez y se guardan en memoria por (ruta, mtime, tamaño) para no gastar CPU en
  cada request.
- Los estáticos pedidos con ``?v=N`` (cache-busting ya usado en templates) se
  sirven con ``Cache-Control: immutable`` de 1 año; los demás conservan el
  comportamiento por defecto de Flask (revalidación con ETag/304).

Nunca se tocan respuestas en streaming (SSE), rangos parciales, códigos != 200
ni respuestas que ya tengan Content-Encoding.
"""
from __future__ import annotations

import gzip
import os
import threading

_COMPRESSIBLE = frozenset((
    'text/html', 'text/css', 'text/plain', 'text/javascript', 'text/xml',
    'application/javascript', 'application/x-javascript', 'application/json',
    'application/manifest+json', 'application/xml', 'image/svg+xml',
))
_MIN_SIZE = 1024
_LEVEL = 6
_STATIC_CACHE_MAX = 64
_STATIC_IMMUTABLE = 'public, max-age=31536000, immutable'

_static_gz: dict[tuple, bytes] = {}
_static_lock = threading.Lock()


def _weaken_etag(resp) -> None:
    etag, weak = resp.get_etag()
    if etag and not weak:
        resp.set_etag(etag, weak=True)


def _gzip_static(app, request) -> bytes | None:
    filename = (request.view_args or {}).get('filename')
    folder = app.static_folder
    if not filename or not folder:
        return None
    path = os.path.realpath(os.path.join(folder, filename))
    if not path.startswith(os.path.realpath(folder) + os.sep):
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (path, st.st_mtime_ns, st.st_size)
    data = _static_gz.get(key)
    if data is not None:
        return data
    with open(path, 'rb') as fh:
        data = gzip.compress(fh.read(), _LEVEL)
    with _static_lock:
        if len(_static_gz) >= _STATIC_CACHE_MAX:
            _static_gz.clear()
        _static_gz[key] = data
    return data


def init_compression(app) -> None:
    from flask import request

    @app.after_request
    def _compress_response(resp):
        try:
            is_static = request.endpoint == 'static'
            if is_static and resp.status_code in (200, 304) and request.args.get('v'):
                resp.headers['Cache-Control'] = _STATIC_IMMUTABLE

            if (resp.status_code != 200
                    or resp.mimetype not in _COMPRESSIBLE
                    or 'Content-Encoding' in resp.headers
                    or request.method == 'HEAD'
                    or request.headers.get('Range')
                    or 'gzip' not in (request.headers.get('Accept-Encoding') or '').lower()):
                return resp

            old_iter = None
            if resp.direct_passthrough:
                if not is_static:
                    return resp
                data = _gzip_static(app, request)
                if data is None:
                    return resp
                old_iter = resp.response
                resp.direct_passthrough = False
            else:
                if resp.is_streamed:
                    return resp
                raw = resp.get_data()
                if len(raw) < _MIN_SIZE:
                    return resp
                data = gzip.compress(raw, _LEVEL)

            resp.set_data(data)
            resp.headers['Content-Encoding'] = 'gzip'
            resp.vary.add('Accept-Encoding')
            _weaken_etag(resp)
            close = getattr(old_iter, 'close', None)
            if close:
                try:
                    close()
                except Exception:
                    pass
        except Exception:
            # La compresión es una optimización: ante cualquier fallo se
            # devuelve la respuesta original intacta.
            pass
        return resp
