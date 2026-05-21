"""Cliente HTTP → Render /api/argus-admin/v1"""
from __future__ import annotations

import json
import time

import requests

from .config_local import device_id, load


def _parse_json_response(r: requests.Response, context: str) -> dict:
    text = (r.text or '').strip()
    if not text:
        hint = ''
        if r.status_code in (502, 503, 504):
            hint = ' Render puede estar dormido; esperá 30 s y probá de nuevo.'
        elif r.status_code == 404:
            hint = (
                ' La API /api/argus-admin/v1 no existe en ese servidor.\n'
                'Hay que hacer deploy del web_app a Render (git push), o usar panel local:\n'
                'api_url = http://127.0.0.1:8080 (con INICIAR_PANEL_LOCAL.bat).'
            )
        raise RuntimeError(
            f'{context}: el servidor no devolvió datos (HTTP {r.status_code}).{hint}'
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        snippet = text[:240].replace('\n', ' ')
        raise RuntimeError(
            f'{context}: respuesta no es JSON (HTTP {r.status_code}). '
            f'¿URL correcta? Fragmento: {snippet}'
        ) from e


def _network_error(context: str, url: str, exc: Exception) -> RuntimeError:
    msg = str(exc).lower()
    if 'timeout' in msg or isinstance(exc, requests.Timeout):
        return RuntimeError(
            f'{context}: tiempo de espera agotado.\n'
            'Si usás Render gratis, el servidor puede tardar ~30 s en despertar. Probá otra vez.'
        )
    return RuntimeError(
        f'{context}: no hay conexión con el servidor.\n'
        f'URL: {url}\nDetalle: {exc}'
    )


def _request(method: str, url: str, context: str, *, retry_cold_start: bool = True, **kwargs) -> requests.Response:
    kwargs.setdefault('timeout', 60)
    last_exc: Exception | None = None
    for attempt in range(2 if retry_cold_start else 1):
        try:
            r = requests.request(method, url, **kwargs)
            if retry_cold_start and attempt == 0 and r.status_code in (502, 503, 504):
                time.sleep(28)
                continue
            return r
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            if attempt == 0 and retry_cold_start:
                time.sleep(5)
                continue
            raise _network_error(context, url, e) from e
    if last_exc:
        raise _network_error(context, url, last_exc)
    raise RuntimeError(f'{context}: error de red desconocido')


class ArgusAdminApi:
    def __init__(self, token: str | None = None):
        self.token = token
        self.cfg = load()
        self.base = (self.cfg.get('api_url') or '').rstrip('/')
        if not self.base:
            raise RuntimeError('Falta api_url en %APPDATA%\\ArgusAdmin\\config.json')
        self.dev = device_id()

    def _headers(self, *, with_token: bool = True) -> dict:
        h = {'Content-Type': 'application/json', 'X-Argus-Admin-Device': self.dev}
        if with_token and self.token:
            h['X-Argus-Admin-Token'] = self.token
        return h

    def check_api_available(self, *, fast: bool = False) -> tuple[bool, str]:
        """Comprueba que Render (o local) expone ArgusAdmin API."""
        url = f'{self.base}/api/argus-admin/v1/status'
        try:
            r = _request(
                'GET',
                url,
                'API ArgusAdmin',
                retry_cold_start=not fast,
                timeout=12 if fast else 60,
            )
        except RuntimeError as e:
            return False, str(e)
        if r.status_code == 404:
            return False, (
                f'El servidor {self.base} no tiene ArgusAdmin API (404).\n\n'
                'Solución producción: subí a Render el código con web_app/argus_admin_api.py '
                '(git push → auto-deploy).\n\n'
                'Solución temporal en tu PC:\n'
                '1) BAT\\INICIAR_PANEL_LOCAL.bat\n'
                '2) En %APPDATA%\\ArgusAdmin\\config.json → '
                '"api_url": "http://127.0.0.1:8080"\n'
                '3) Regrabar voz'
            )
        try:
            data = _parse_json_response(r, 'API ArgusAdmin')
        except RuntimeError as e:
            return False, str(e)
        if not r.ok:
            return False, data.get('error') or f'HTTP {r.status_code}'
        return True, f"API OK ({data.get('product', 'ArgusAdmin')})"

    def login(self, username: str, password: str) -> dict:
        r = _request(
            'POST',
            f'{self.base}/api/argus-admin/v1/login',
            'Login',
            json={'username': username, 'password': password, 'device_id': self.dev},
        )
        data = _parse_json_response(r, 'Login')
        if not r.ok:
            err = data.get('error') if isinstance(data, dict) else None
            raise RuntimeError(err or f'Login falló ({r.status_code})')
        self.token = data.get('token')
        if not self.token:
            raise RuntimeError('Login OK pero el servidor no devolvió token.')
        return data

    def enroll_voice(self, fp_hash: str, extra_hashes: list[str] | None = None) -> dict:
        payload: dict = {'fingerprint_hash': fp_hash}
        if extra_hashes:
            payload['fingerprint_hashes'] = extra_hashes
        r = _request(
            'POST',
            f'{self.base}/api/argus-admin/v1/voice/enroll',
            'Registro de voz',
            json=payload,
            headers=self._headers(),
        )
        data = _parse_json_response(r, 'Registro de voz')
        if not r.ok:
            err = data.get('error') if isinstance(data, dict) else None
            raise RuntimeError(err or f'Enroll falló ({r.status_code})')
        return data

    def unlock_voice(self, username: str, password: str, fp_hash: str) -> dict:
        r = _request(
            'POST',
            f'{self.base}/api/argus-admin/v1/voice/unlock',
            'Desbloqueo',
            json={
                'username': username,
                'password': password,
                'device_id': self.dev,
                'fingerprint_hash': fp_hash,
            },
        )
        data = _parse_json_response(r, 'Desbloqueo')
        if not r.ok:
            raise RuntimeError(data.get('error') or f'Desbloqueo falló ({r.status_code})')
        self.token = data.get('token')
        if not self.token:
            raise RuntimeError('Desbloqueo OK pero sin token.')
        return data

    def overview(self) -> dict:
        r = _request(
            'GET',
            f'{self.base}/api/argus-admin/v1/overview',
            'Overview',
            headers=self._headers(),
            retry_cold_start=False,
        )
        if not r.ok:
            return {'error': f'HTTP {r.status_code}', 'detail': (r.text or '')[:200]}
        try:
            return _parse_json_response(r, 'Overview')
        except RuntimeError as e:
            return {'error': str(e)}

    def get_config(self) -> dict:
        r = _request(
            'GET',
            f'{self.base}/api/argus-admin/v1/config',
            'Config',
            headers=self._headers(),
            retry_cold_start=False,
        )
        if not r.ok:
            return {}
        try:
            data = _parse_json_response(r, 'Config')
            return data.get('config', {}) if isinstance(data, dict) else {}
        except RuntimeError:
            return {}

    def put_config(self, cfg: dict) -> dict:
        r = _request(
            'PUT',
            f'{self.base}/api/argus-admin/v1/config',
            'Guardar config',
            json={'config': cfg},
            headers=self._headers(),
            retry_cold_start=False,
        )
        if not r.ok:
            return {'error': (r.text or '')[:200]}
        try:
            return _parse_json_response(r, 'Guardar config')
        except RuntimeError as e:
            return {'error': str(e)}
