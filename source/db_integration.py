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
        self.machine_name = os.environ.get('COMPUTERNAME', 'Unknown')
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
            
            scan_data = {
                'token': self.scan_token,
                'machine_id': self.machine_id,
                'machine_name': self.machine_name,
                'ip_address': self.user_info.get('ip_address'),
                'country': self.user_info.get('country'),
                'minecraft_username': minecraft_username
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
            # Preparar resultados para la API
            results = []
            for issue in issues_found:
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
                    'ai_confidence': issue.get('ai_confidence', 0)
                })
            
            payload = {
                'status': 'completed',
                'total_files_scanned': total_files_scanned,
                'total_dirs_scanned': total_dirs_scanned,
                'issues_found': len(issues_found),
                'scan_duration': scan_duration,
                'results': results
            }
            
            url = f"{self.api_url}/api/scans/{self.scan_id}/results"
            print(f"📤 Enviando POST a: {url}")
            print(f"📤 Payload: {len(results)} resultados, {total_files_scanned} archivos")
            
            response = requests.post(
                url,
                json=payload,
                timeout=30
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
            print(f"❌ ERROR: Timeout al conectar con la API (30s)")
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

