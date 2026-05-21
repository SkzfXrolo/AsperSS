"""
Integración del Scanner con Base de Datos y API REST
Permite al scanner enviar resultados a la BD y recibir análisis de IA
"""
import sqlite3
import requests
import json
import os
from datetime import datetime

try:
    from user_info_collector import UserInfoCollector
    USER_INFO_AVAILABLE = True
except ImportError:
    USER_INFO_AVAILABLE = False
    UserInfoCollector = None

class DatabaseIntegration:
    """Clase para integrar el scanner con la base de datos y API"""
    
    def __init__(self, api_url='http://localhost:5000', api_key=None, scan_token=None):
        self.api_url = api_url
        self.api_key = api_key
        self.scan_token = scan_token
        self.scan_id = None
        self.machine_id = self._get_machine_id()
        import socket
        self.machine_name = (
            os.environ.get('COMPUTERNAME') or
            os.environ.get('HOSTNAME') or
            socket.gethostname() or
            'Unknown'
        )
        self.app = None  # Referencia a la app principal para acceso a datos detectados
        
        # Recopilar información del usuario
        self.user_info = {}
        if USER_INFO_AVAILABLE:
            try:
                collector = UserInfoCollector()
                self.user_info = collector.collect_all_info()
            except Exception as e:
                print(f"⚠️ Error recopilando información del usuario: {e}")
                self.user_info = {}
    
    def _get_machine_id(self):
        """Genera un ID único para la máquina"""
        import platform
        import hashlib
        
        # Combinar información única de la máquina
        machine_info = f"{platform.node()}{platform.processor()}{platform.machine()}"
        return hashlib.sha256(machine_info.encode()).hexdigest()[:16]
    
    def start_scan(self):
        """Inicia un escaneo en la API"""
        if not self.scan_token:
            print("⚠️ No hay token de escaneo configurado")
            return False
        
        try:
            # Preparar datos con información del usuario
            # Priorizar username detectado desde conexiones activas sobre archivos
            minecraft_username = None
            if hasattr(self, 'app') and hasattr(self.app, 'detected_minecraft_username'):
                minecraft_username = self.app.detected_minecraft_username
            
            if not minecraft_username:
                minecraft_username = self.user_info.get('minecraft_username')
            
            # Visual #50 — incluir versión del scanner que generó este scan
            _scn_ver = ''
            try:
                if self.app is not None:
                    _scn_ver = getattr(self.app, 'scanner_version', '') or ''
                if not _scn_ver:
                    try:
                        from config.version import SCANNER_VERSION as _SV
                        _scn_ver = _SV
                    except Exception:
                        try:
                            from main import SCANNER_VERSION as _SV  # type: ignore
                            _scn_ver = _SV
                        except Exception:
                            pass
            except Exception:
                _scn_ver = ''

            scan_data = {
                'token': self.scan_token,
                'machine_id': self.machine_id,
                'machine_name': self.machine_name,
                'ip_address': self.user_info.get('ip_address'),
                'country': self.user_info.get('country'),
                'minecraft_username': minecraft_username,
                'os': self.user_info.get('os', 'Windows'),
                'os_version': self.user_info.get('os_version', ''),
                'mc_version': self.user_info.get('mc_version'),
                'mc_launcher': self.user_info.get('mc_launcher'),
                'mc_mods': self.user_info.get('mc_mods', []),
                'java_agents': self.user_info.get('java_agents', []),
                'scanner_version': _scn_ver,
            }
            
            response = requests.post(
                f"{self.api_url}/api/scans",
                json=scan_data,
                timeout=10
            )
            
            if response.status_code == 201:
                data = response.json()
                self.scan_id = data.get('scan_id')
                
                # Mostrar información recopilada
                if self.user_info.get('minecraft_username'):
                    print(f"👤 Username de Minecraft: {self.user_info['minecraft_username']}")
                if self.user_info.get('country'):
                    print(f"🌍 País detectado: {self.user_info['country']}")
                
                # Mostrar historial de bans si existe
                if data.get('has_ban_history'):
                    previous_bans = data.get('previous_bans', [])
                    print(f"⚠️ Historial de bans encontrado: {len(previous_bans)} ban(s) previo(s)")
                    for ban in previous_bans[:3]:  # Mostrar primeros 3
                        print(f"   - {ban.get('hack_type', 'Desconocido')}: {ban.get('reason', 'Sin razón')}")
                
                print(f"✅ Escaneo iniciado en API - ID: {self.scan_id}")
                return True
            else:
                print(f"❌ Error al iniciar escaneo: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error de conexión con API: {e}")
            return False
    
    def take_screenshot(self):
        """Captures the current screen and returns a base64-encoded JPEG string, or None on failure."""
        try:
            import base64
            from io import BytesIO
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
            except Exception:
                try:
                    import mss, mss.tools
                    with mss.mss() as sct:
                        sct_img = sct.grab(sct.monitors[0])
                        from PIL import Image
                        img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
                except Exception:
                    return None
            buf = BytesIO()
            img.convert('RGB').save(buf, format='JPEG', quality=50, optimize=True)
            return base64.b64encode(buf.getvalue()).decode('utf-8')
        except Exception as e:
            print(f"⚠️ Error capturando pantalla: {e}")
            return None

    def submit_results(self, issues_found, total_files_scanned, scan_duration, total_dirs_scanned=0):
        """Envía resultados del escaneo a la API"""
        print(f"\n{'='*60}")
        print(f"📤 ===== ENVIANDO RESULTADOS A LA API ======")
        print(f"📤 API URL: {self.api_url}")
        print(f"📤 Scan Token: {self.scan_token[:20] + '...' if self.scan_token else 'NO CONFIGURADO'}")
        print(f"📤 Scan ID: {self.scan_id}")
        print(f"📤 Issues encontrados: {len(issues_found)}")
        print(f"📤 Archivos escaneados: {total_files_scanned}")
        print(f"📤 Duración: {scan_duration}s")
        print(f"{'='*60}\n")
        
        # Verificar que tenemos token antes de intentar enviar
        if not self.scan_token:
            print("❌ ERROR: No hay token de escaneo configurado")
            print("💡 Por favor, autentícate primero con un token válido")
            return False
        
        if not self.scan_id:
            print("⚠️ No hay scan_id, iniciando escaneo...")
            if not self.start_scan():
                print("❌ No se pudo iniciar el escaneo en la API")
                return False
            print(f"✅ Escaneo iniciado - Scan ID: {self.scan_id}")
        
        try:
            # Deduplicar — múltiples funciones pueden detectar el mismo archivo
            seen_keys: set = set()
            deduped: list = []
            for _iss in issues_found:
                _key = (_iss.get('tipo', ''), _iss.get('archivo', '') or _iss.get('ruta', ''), _iss.get('nombre', ''))
                if _key not in seen_keys:
                    seen_keys.add(_key)
                    deduped.append(_iss)
            issues_found = deduped

            # ─── Filtro pre-envío: descartar basura obvia para garantizar
            #     que jamás llegue ruido al servidor / panel ──────────────────
            import re as _pre_re
            _PRE_GARBAGE_RE = _pre_re.compile(
                r'\bLMEM\b|Windows\.Data\.|Matrix3x2|\.CenterX|\.CenterY|'
                r'ItemReference|MEOW\b|CloudData|RevealBrush|XamlAnim|'
                r'D2D1\.|DCompositionBrush|\\u[0-9a-f]{4}|'
                r'^[\x00-\x08\x0b\x0c\x0e-\x1f]{2,}',
                _pre_re.IGNORECASE
            )
            _PRE_NONPRINT_RE = _pre_re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
            _PRE_HIGH_RUN_RE = _pre_re.compile(r'[\u0080-\uFFFF]{4,}')

            def _pre_is_garbage(s: str) -> bool:
                if not s:
                    return False
                s = str(s)
                if len(s) > 600:
                    return True
                if len(_PRE_NONPRINT_RE.findall(s)) >= 2:
                    return True
                if _PRE_HIGH_RUN_RE.search(s):
                    return True
                if _PRE_GARBAGE_RE.search(s):
                    return True
                alnum = sum(1 for c in s if c.isalnum() or c in ' .\\/_-:()[]')
                if len(s) >= 12 and alnum / max(1, len(s)) < 0.30:
                    return True
                return False

            _PRE_SAFE_FRAGS = (
                'windows\\system32', 'windows\\syswow64', 'windows\\winsxs',
                'windows\\servicing', 'windows\\softwaredistribution',
                'program files\\microsoft', 'program files (x86)\\microsoft',
                'programdata\\microsoft', 'programdata\\package cache',
                'appdata\\local\\packages', 'appdata\\local\\microsoft',
                'webview2runtime', 'site-packages', 'node_modules',
                '.gradle\\caches', '.gradle\\wrapper', '.m2\\repository',
                'jetbrains\\intellij', 'jetbrains\\toolbox',
                'visual studio code', 'cursor\\',
                'lunar client', 'lunarclient', 'feathermc',
                'badlion client', 'labymod',
                'easyanticheat', 'battleye', 'vanguard',
                'argusscanner', 'minecraftsstool',  # propio scanner
            )
            _PRE_ZERO_RISK_TYPES = {
                'texture_pack', 'texture_pack_xray', 'texture_pack_analysis',
                'resource_pack', 'resource_pack_xray', 'event_logs',
            }

            def _pre_is_fp(_iss: dict) -> bool:
                # FILE_ACTIVITY (historial del tab Logs): no aplicar el filtro de
                # paths "seguros" — son entradas informacionales de Recycle Bin /
                # Prefetch / USN / walk de carpetas user, y CAEN justo en rutas
                # como AppData/Windows que están en _PRE_SAFE_FRAGS por diseño.
                _cat = (_iss.get('categoria') or '').upper()
                if _cat == 'FILE_ACTIVITY':
                    _nombre = _iss.get('nombre') or _iss.get('archivo') or ''
                    _ruta_raw = _iss.get('ruta') or _iss.get('archivo') or ''
                    # Solo descartar basura binaria (parsers rotos)
                    if _pre_is_garbage(_nombre) or _pre_is_garbage(_ruta_raw):
                        return True
                    return False
                _tipo = (_iss.get('tipo') or '').lower().replace(' ', '_')
                if _tipo in _PRE_ZERO_RISK_TYPES:
                    return True
                _nombre = _iss.get('nombre') or _iss.get('archivo') or ''
                _ruta_raw = _iss.get('ruta') or _iss.get('archivo') or ''
                if _pre_is_garbage(_nombre) or _pre_is_garbage(_ruta_raw):
                    return True
                if not str(_nombre).strip() and not str(_ruta_raw).strip():
                    return True
                _ruta_n = str(_ruta_raw).lower().replace('/', '\\')
                while '\\\\' in _ruta_n:
                    _ruta_n = _ruta_n.replace('\\\\', '\\')
                _combined = _ruta_n + '|' + str(_nombre).lower()
                # No descartar hacks definitivos aunque estén bajo AppData/Temp
                try:
                    from config.hack_signatures import combined_path_indicates_hack
                    if combined_path_indicates_hack(str(_nombre), _ruta_n, _ruta_n):
                        return False
                except ImportError:
                    pass
                if _tipo in (
                    'blacklisted_mod', 'dll_injection_java', 'injected_dll',
                    'javaagent_injection', 'injector_process', 'ghost_client_config',
                    'browser_visited_hack', 'browser_download_hack',
                ):
                    return False
                if any(f in _combined for f in _PRE_SAFE_FRAGS):
                    return True
                return False

            _before_pre = len(issues_found)
            issues_found = [i for i in issues_found if not _pre_is_fp(i)]
            if len(issues_found) < _before_pre:
                print(f"🧹 Pre-filter: {_before_pre} → {len(issues_found)} ({_before_pre - len(issues_found)} FP descartados antes del envío)")

            # Preparar resultados para la API — separamos detecciones (sujetas a cap)
            # de FILE_ACTIVITY (historial informacional, sin cap pero con su propio máx).
            _detections   = [i for i in issues_found
                             if (i.get('categoria') or '').upper() != 'FILE_ACTIVITY']
            _file_history = [i for i in issues_found
                             if (i.get('categoria') or '').upper() == 'FILE_ACTIVITY']

            _severity_order = {'CRITICAL': 0, 'SOSPECHOSO': 1, 'POCO_SOSPECHOSO': 2, 'NORMAL': 3}
            sorted_issues = sorted(
                _detections,
                key=lambda x: (_severity_order.get(x.get('alerta', 'NORMAL'), 3), -x.get('confidence', 0))
            )
            MAX_RESULTS = 200
            if len(sorted_issues) > MAX_RESULTS:
                print(f"⚠️ Truncando detecciones: {len(sorted_issues)} → {MAX_RESULTS} (por severidad)")
                sorted_issues = sorted_issues[:MAX_RESULTS]

            # Cap separado para historial de archivos: hasta 5000 (preservando los más recientes)
            MAX_FILE_HISTORY = 1200
            if len(_file_history) > MAX_FILE_HISTORY:
                _file_history.sort(key=lambda r: (r.get('extra') or {}).get('ts', 0), reverse=True)
                print(f"⚠️ Truncando historial de archivos: {len(_file_history)} → {MAX_FILE_HISTORY}")
                _file_history = _file_history[:MAX_FILE_HISTORY]

            # Combinamos: detecciones primero, luego el historial de archivos
            sorted_issues = list(sorted_issues) + list(_file_history)

            results = []
            for issue in sorted_issues:
                # Sanitizar 'extra': solo claves serializables y valores cortos
                raw_extra = issue.get('extra') or {}
                clean_extra = {}
                if isinstance(raw_extra, dict):
                    for k, v in raw_extra.items():
                        if not isinstance(k, str):
                            continue
                        if isinstance(v, (str, int, float, bool)) or v is None:
                            if isinstance(v, str) and len(v) > 500:
                                v = v[:500]
                            clean_extra[k] = v
                results.append({
                    'tipo': issue.get('tipo', ''),
                    'nombre': issue.get('nombre', ''),
                    'ruta': issue.get('ruta', ''),
                    'archivo': issue.get('archivo', ''),
                    'categoria': issue.get('categoria', ''),
                    'alerta': issue.get('alerta', ''),
                    'confidence': issue.get('confidence', 0),
                    'detected_patterns': issue.get('detected_patterns', []),
                    'obfuscation': issue.get('obfuscation', False),
                    'file_hash': issue.get('file_hash', ''),
                    'ai_analysis': issue.get('ai_analysis', ''),
                    'ai_confidence': issue.get('ai_confidence', 0),
                    'extra': clean_extra,
                })

            # Calcular risk_score 0-100 agregando scores por severidad
            _risk = 0
            _ALERTA_WEIGHTS = {
                'CRITICAL':          25,
                'MUY_SOSPECHOSO':    16,
                'SOSPECHOSO':        12,
                'PAGINA_SOSPECHOSA':  6,
                'POCO_SOSPECHOSO':    4,
                'NORMAL':             1,
            }
            _NON_INST_FRAGS = ('\\downloads\\', '\\desktop\\', '/downloads/', '/desktop/', '\\temp\\', '/temp/')
            _KNOWN_RISK_CLIENTS = ['vape','entropy','whiteout','liquidbounce','wurst','sigma','flux',
                'future','astolfo','ghost','rise','moon','drip','meteor','aristois','tenacity',
                'vertex','inertia','salhack','slinky','reflex','rage','biscuit','thunder']
            _seen_risk_clients: set = set()
            for _iss in issues_found:
                # FILE_ACTIVITY es historial informacional puro: NO suma al risk score.
                if (_iss.get('categoria') or '').upper() == 'FILE_ACTIVITY':
                    continue
                _alerta = _iss.get('alerta', 'NORMAL')
                _conf = float(_iss.get('confidence') or 0)
                if _conf <= 1:
                    _conf = _conf * 100
                # Reduce weight for files outside the Minecraft instance
                _ruta = (_iss.get('ruta', '') or _iss.get('archivo', '') or '').lower()
                _inst_mult = 0.55 if any(f in _ruta for f in _NON_INST_FRAGS) else 1.0
                # Each hack client counts only once toward risk (avoid 5x slinky = 100)
                _iss_text = (_iss.get('nombre', '') + ' ' + _iss.get('tipo', '')).lower()
                _client_key = next((c for c in _KNOWN_RISK_CLIENTS if c in _iss_text), None)
                if _client_key:
                    if _client_key in _seen_risk_clients:
                        continue
                    _seen_risk_clients.add(_client_key)
                _item_score = _ALERTA_WEIGHTS.get(_alerta, 1) * min(_conf / 100, 1) * _inst_mult
                _risk += _item_score
            risk_score = min(100, int(_risk))

            screenshot_b64 = self.take_screenshot()
            payload = {
                'status': 'completed',
                'total_files_scanned': total_files_scanned,
                'total_dirs_scanned': total_dirs_scanned,
                'issues_found': len(issues_found),
                'scan_duration': scan_duration,
                'results': results,
                'screenshot': screenshot_b64,
                'risk_score': risk_score,
            }

            url = f"{self.api_url}/api/scans/{self.scan_id}/results"
            print(f"📤 Enviando POST a: {url}")
            print(f"📤 Payload: {len(results)} resultados, {total_files_scanned} archivos")

            response = requests.post(
                url,
                json=payload,
                timeout=60
            )
            
            print(f"📤 Respuesta recibida:")
            print(f"   - Status Code: {response.status_code}")
            print(f"   - Response: {response.text[:200]}")
            
            if response.status_code == 200:
                print(f"✅ Resultados enviados exitosamente a API - {len(issues_found)} issues")
                print(f"{'='*60}\n")
                return True
            else:
                print(f"❌ Error al enviar resultados:")
                print(f"   - Status: {response.status_code}")
                print(f"   - Response: {response.text}")
                print(f"{'='*60}\n")
                return False
        except requests.exceptions.Timeout:
            print(f"❌ ERROR: Timeout al conectar con la API (60s)")
            print(f"   - URL: {self.api_url}")
            print(f"   - Esto puede indicar que la API está lenta o no responde")
            print(f"{'='*60}\n")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"❌ ERROR: No se pudo conectar con la API")
            print(f"   - URL: {self.api_url}")
            print(f"   - Error: {str(e)}")
            print(f"   - Verifica que la API esté corriendo y accesible")
            print(f"{'='*60}\n")
            return False
        except Exception as e:
            import traceback
            print(f"❌ ERROR inesperado al enviar resultados:")
            print(f"   - Error: {str(e)}")
            print(f"   - Traceback:")
            print(traceback.format_exc())
            print(f"{'='*60}\n")
            return False
    
    def get_ai_analysis(self, issue):
        """Obtiene análisis de IA para un issue específico"""
        # TODO: Implementar llamada a servicio de IA
        # Por ahora retorna análisis básico
        return {
            'analysis': 'Análisis de IA pendiente de implementación',
            'confidence': 0.5
        }
    
    def check_for_updates(self, current_version='1.0.0'):
        """Verifica si hay actualizaciones disponibles"""
        try:
            response = requests.get(
                f"{self.api_url}/api/versions/latest",
                params={'current_version': current_version},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('update_available', False), data
            else:
                return False, None
        except Exception as e:
            print(f"❌ Error al verificar actualizaciones: {e}")
            return False, None

