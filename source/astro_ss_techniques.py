"""
Técnicas de detección inspiradas en AstroSS
Métodos específicos para detectar hacks mediante análisis de memoria y procesos del sistema
"""
import os
import psutil
import subprocess
import time
import requests
import tempfile
from typing import List, Dict

class AstroSSTechniques:
    """Técnicas de detección de AstroSS"""
    
    def __init__(self):
        self.strings2_path = None
        self.download_strings2()
    
    def download_strings2(self):
        """Descarga strings2.exe si no está disponible"""
        try:
            strings2_url = 'https://github.com/glmcdona/strings2/raw/master/x64/Release/strings.exe'
            temp_dir = os.path.join(os.environ.get('TEMP', tempfile.gettempdir()), 'AstroSS')
            
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            strings2_path = os.path.join(temp_dir, 'strings2.exe')
            
            if not os.path.exists(strings2_path):
                print("📥 Descargando strings2.exe para análisis de memoria...")
                response = requests.get(strings2_url, timeout=30)
                if response.status_code == 200:
                    with open(strings2_path, 'wb') as f:
                        f.write(response.content)
                    print("✅ strings2.exe descargado")
                else:
                    print("⚠️ No se pudo descargar strings2.exe")
                    return None
            
            self.strings2_path = strings2_path
            return strings2_path
        except Exception as e:
            print(f"⚠️ Error descargando strings2.exe: {e}")
            return None
    
    def get_pid_by_name(self, name: str, service: bool = False) -> int:
        """Obtiene el PID de un proceso por nombre"""
        try:
            if service:
                # Para servicios, usar tasklist /svc
                result = subprocess.run(
                    ['tasklist', '/svc', '/FI', f'Services eq {name}'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if name in line:
                            parts = line.split()
                            if len(parts) > 1:
                                try:
                                    return int(parts[1])
                                except:
                                    pass
            else:
                # Para procesos normales
                for proc in psutil.process_iter(['pid', 'name']):
                    if proc.info['name'].lower() == name.lower():
                        return proc.info['pid']
        except Exception as e:
            print(f"Error obteniendo PID de {name}: {e}")
        return None
    
    def dump_strings_from_pid(self, pid: int) -> List[str]:
        """Extrae strings de un proceso usando strings2.exe"""
        if not self.strings2_path or not os.path.exists(self.strings2_path):
            return []
        
        try:
            drive_letter = os.getcwd().split('\\')[0] + '\\'
            cmd = f'{self.strings2_path} -pid {pid} -raw -nh'
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                strings = result.stdout.replace("\\\\", "/")
                strings = list(set(strings.split("\r\n")))
                return strings
        except Exception as e:
            print(f"Error haciendo dump de strings del PID {pid}: {e}")
        
        return []
    
    def detect_recording_software(self) -> List[Dict]:
        """Detecta software de grabación (técnica de AstroSS)"""
        issues = []
        try:
            recording_softwares = {
                'bdcam.exe': 'Bandicam',
                'action.exe': 'Action',
                'obs64.exe': 'OBS',
                'dxtory': 'Dxtory',
                'nvidia share': 'Geforce Experience',
                'camtasia': 'Camtasia',
                'fraps': 'Fraps',
                'screencast': 'Screencast'
            }
            
            tasks = str(subprocess.check_output('tasklist', shell=True)).lower()
            found = [x for x in recording_softwares if x in tasks]
            
            for software in found:
                issues.append({
                    'tipo': 'recording_software',
                    'nombre': f"{recording_softwares[software]} detectado",
                    'ruta': 'Procesos Activos',
                    'archivo': software,
                    'alerta': 'INFO',
                    'categoria': 'RECORDING'
                })
        except Exception as e:
            print(f"Error detectando software de grabación: {e}")
        
        return issues
    
    def check_modification_times(self) -> List[Dict]:
        """Verifica tiempos de modificación (técnica de AstroSS)"""
        issues = []
        try:
            win_username = os.getlogin()
            drive_letter = os.getcwd().split('\\')[0] + '\\'
            
            # Obtener SID del usuario
            result = subprocess.run(
                f'wmic useraccount where name="{win_username}" get sid',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\r\r\n')
                if len(lines) > 1:
                    SID = lines[1].strip()
                    recycle_bin_path = f"{drive_letter}$Recycle.Bin\\{SID}"
                    
                    if os.path.exists(recycle_bin_path):
                        mod_time = os.path.getmtime(recycle_bin_path)
                        mod_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))
                        
                        # Verificar si fue modificado recientemente (últimas 24 horas)
                        if time.time() - mod_time < 86400:
                            issues.append({
                                'tipo': 'recycle_bin_recent',
                                'nombre': f"Papelera modificada recientemente: {mod_time_str}",
                                'ruta': recycle_bin_path,
                                'archivo': 'Recycle Bin',
                                'alerta': 'SOSPECHOSO',
                                'categoria': 'MODIFICATION_TIMES'
                            })
            
            # Verificar tiempo de inicio de Explorer
            explorer_pid = self.get_pid_by_name('explorer.exe')
            if explorer_pid:
                try:
                    proc = psutil.Process(explorer_pid)
                    start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(proc.create_time()))
                    # Verificar si fue iniciado recientemente
                    if time.time() - proc.create_time() < 3600:  # Última hora
                        issues.append({
                            'tipo': 'explorer_recent_start',
                            'nombre': f"Explorer iniciado recientemente: {start_time}",
                            'ruta': f"PID: {explorer_pid}",
                            'archivo': 'explorer.exe',
                            'alerta': 'INFO',
                            'categoria': 'MODIFICATION_TIMES'
                        })
                except:
                    pass
            
            # Verificar tiempo de inicio de Minecraft/Java
            for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                try:
                    if proc.info['name'].lower() in ['javaw.exe', 'java.exe']:
                        start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(proc.info['create_time']))
                        # Verificar si fue iniciado recientemente
                        if time.time() - proc.info['create_time'] < 3600:  # Última hora
                            issues.append({
                                'tipo': 'minecraft_recent_start',
                                'nombre': f"Minecraft iniciado recientemente: {start_time}",
                                'ruta': f"PID: {proc.info['pid']}",
                                'archivo': proc.info['name'],
                                'alerta': 'INFO',
                                'categoria': 'MODIFICATION_TIMES'
                            })
                except:
                    continue
        except Exception as e:
            print(f"Error verificando tiempos de modificación: {e}")
        
        return issues
    
    def in_instance_checks(self) -> List[Dict]:
        """Checks dentro de la instancia de Minecraft (técnica de AstroSS)"""
        issues = []
        
        if not self.strings2_path:
            return issues
        
        try:
            # Buscar proceso javaw.exe
            javaw_pid = None
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'].lower() == 'javaw.exe':
                    javaw_pid = proc.info['pid']
                    break
            
            if not javaw_pid:
                return issues
            
            # Hacer dump de strings del proceso
            javaw_strings = self.dump_strings_from_pid(javaw_pid)
            
            # Patrones de hacks conocidos (versión expandida basada en config.py de AstroSS)
            hack_patterns = {
                'net/impactclient': 'Impact Client',
                '9HzN[Lnet/impactclient/6n;': 'Impact Client',
                'SqtkUVg': 'Vape v3 #1',
                'CABzZzJ)': 'Vape v3 #2',
                'erouax/instavape': 'Wax Vape Mod',
                'com/sun/jna/z/a/e/a/a/a/f': 'Vape Cracked #1',
                'com/sun/jna/z/Main': 'Vape Cracked #2',
                'manthe, aimassist': 'Vape Cracked #3',
                'com.sun.jna.zagg': 'Vape Cracked #4',
                '2.47-KILL': 'Vape Cracked #5',
                'yCcADi': 'Vape Cracked #7',
                '>KRTal': 'Vape Cracked #8',
                '*YXY*[': 'Vape Cracked #9',
                ',#I)!': 'Vape Cracked #10 [FORGE ONLY]',
                'kcc((k': 'Vape Variation #2',
                'C()[Lf/r;': 'Vape Variation #3',
                '(ILjava/lang/Object;[S)V': 'Vape Variation #4',
                'hakery.c': 'Latemod Injection Client #1',
                'hakery.club': 'Latemod Injection Client #2',
                'liquidbounce': 'LiquidBounce',
                'net/wurstclient': 'Wurst Client',
                'net/ccbluex/LiquidBounce': 'LiquidBounce Injection',
                'future/api': 'Future Client',
                'sigma': 'Sigma Client',
                'flux': 'Flux Client',
                'entropy': 'Entropy Client',
                'whiteout': 'Whiteout Client',
                'xray': 'XRay Mod',
                'killaura': 'KillAura',
                'aimbot': 'Aimbot',
                'reach': 'Reach Mod',
                'velocity': 'Velocity Mod',
                'autoclicker': 'AutoClicker',
                'triggerbot': 'Triggerbot',
                'nofall': 'NoFall',
                'scaffold': 'Scaffold',
                'fly': 'Fly',
                'speedhack': 'Speed Hack',
                'esp': 'ESP',
                'wallhack': 'Wallhack'
            }
            
            # Buscar patrones en las strings
            found_patterns = []
            for string in javaw_strings:
                string_lower = string.lower()
                for pattern, hack_name in hack_patterns.items():
                    if pattern.lower() in string_lower:
                        if hack_name not in found_patterns:
                            found_patterns.append(hack_name)
                            issues.append({
                                'tipo': 'in_instance_hack',
                                'nombre': f"{hack_name} detectado en memoria",
                                'ruta': f"PID: {javaw_pid}",
                                'archivo': f"Patrón: {pattern}",
                                'alerta': 'CRITICAL',
                                'categoria': 'MEMORY_ANALYSIS'
                            })
        except Exception as e:
            print(f"Error en in-instance checks: {e}")
        
        return issues
    
    def out_of_instance_checks(self) -> List[Dict]:
        """Checks fuera de la instancia usando DPS (técnica de AstroSS)"""
        issues = []
        
        if not self.strings2_path:
            return issues
        
        try:
            # Obtener PID del servicio DPS
            dps_pid = self.get_pid_by_name('DPS', service=True)
            
            if not dps_pid:
                return issues
            
            # Hacer dump de strings del proceso DPS
            dps_strings = self.dump_strings_from_pid(dps_pid)
            
            # Filtrar strings que contengan .exe!
            exe_strings = [x for x in dps_strings if '.exe!' in x and x.startswith('!!')]
            exe_strings = ['.exe!' + x.split('!')[3] for x in exe_strings if len(x.split('!')) > 3]
            
            # Patrones conocidos de autoclickers y hacks
            dps_patterns = {
                '.exe!2019/03/14:20:01:24': 'OP AutoClicker',
                '.exe!2016/05/30:16:33:32': 'GS AutoClicker',
                '.exe!2016/04/18:16:56:55': 'AutoClicker',
                '.exe!2013/11/26:19:16:05': 'MouseClicker',
                '.exe!2018/10/10:19:00:42': 'Tap',
                '.exe!2018/10/21:19:34:21': 'Ecstasyy',
                '.exe!2018/07/24:11:25:57': 'Apollo Lite',
                '.exe!2018/11/09:01:13:38': 'GhostBytes',
                '.exe!2019/07/05:07:17:50': 'Speed AutoClicker'
            }
            
            # Buscar patrones
            found = [x for x in dps_patterns if x in exe_strings]
            
            for pattern in found:
                issues.append({
                    'tipo': 'out_of_instance_hack',
                    'nombre': f"{dps_patterns[pattern]} detectado en DPS",
                    'ruta': f"PID: {dps_pid}",
                    'archivo': f"Patrón: {pattern}",
                    'alerta': 'CRITICAL',
                    'categoria': 'DPS_ANALYSIS'
                })
        except Exception as e:
            print(f"Error en out-of-instance checks: {e}")
        
        return issues
    
    def detect_jnativehook(self) -> List[Dict]:
        """Detecta autoclickers basados en JNativeHook (técnica de AstroSS)"""
        issues = []
        try:
            user_path = os.path.expanduser("~")
            temp_path = os.path.join(user_path, 'AppData', 'Local', 'Temp')
            
            if os.path.exists(temp_path):
                found = [x for x in os.listdir(temp_path) 
                        if os.path.isfile(os.path.join(temp_path, x)) 
                        and 'JNativeHook' in x 
                        and x.endswith('.dll')]
                
                for file in found:
                    issues.append({
                        'tipo': 'jnativehook_autoclicker',
                        'nombre': f"JNativeHook autoclicker detectado: {file}",
                        'ruta': temp_path,
                        'archivo': file,
                        'alerta': 'CRITICAL',
                        'categoria': 'JNATIVEHOOK'
                    })
        except Exception as e:
            print(f"Error detectando JNativeHook: {e}")
        
        return issues
    
    def detect_executed_deleted_files(self) -> List[Dict]:
        """Detecta archivos ejecutados y luego borrados (técnica de AstroSS)"""
        issues = []
        
        if not self.strings2_path:
            return issues
        
        try:
            drive_letter = os.getcwd().split('\\')[0] + '\\'
            
            # Obtener PID de PcaSvc
            pcasvc_pid = self.get_pid_by_name('PcaSvc', service=True)
            if not pcasvc_pid:
                return issues
            
            # Obtener PID de Explorer
            explorer_pid = self.get_pid_by_name('explorer.exe')
            if not explorer_pid:
                return issues
            
            # Hacer dump de strings de ambos procesos
            pcasvc_strings = self.dump_strings_from_pid(pcasvc_pid)
            explorer_strings = self.dump_strings_from_pid(explorer_pid)
            
            deleted = {}
            
            # Método 01: Comparar strings de PcaSvc con Explorer
            for string in pcasvc_strings:
                string_lower = string.lower()
                if string_lower.startswith(drive_letter.lower()) and string_lower.endswith('.exe'):
                    if not os.path.isfile(string):
                        if string in explorer_strings:
                            filename = string.split('/')[-1]
                            deleted[string] = {
                                'filename': filename,
                                'method': '01'
                            }
            
            # Método 02: Buscar en Explorer strings con 'trace' y 'pcaclient'
            for string in explorer_strings:
                string_lower = string.lower()
                if 'trace' in string_lower and 'pcaclient' in string_lower:
                    # Extraer path del string
                    parts = string.split(',')
                    for part in parts:
                        if '.exe' in part:
                            path = part.strip()
                            if not os.path.isfile(path):
                                filename = path.split('/')[-1]
                                deleted[path] = {
                                    'filename': filename,
                                    'method': '02'
                                }
            
            # Agregar issues para archivos borrados
            for path, info in deleted.items():
                issues.append({
                    'tipo': 'executed_deleted_file',
                    'nombre': f"Archivo ejecutado y borrado: {info['filename']}",
                    'ruta': os.path.dirname(path) if '/' in path else 'Desconocida',
                    'archivo': path,
                    'alerta': 'CRITICAL',
                    'categoria': 'EXECUTED_DELETED',
                    'detection_method': info['method']
                })
        except Exception as e:
            print(f"Error detectando archivos ejecutados y borrados: {e}")
        
        return issues
    
    def scan_all_astro_techniques(self) -> List[Dict]:
        """Ejecuta todas las técnicas de AstroSS"""
        all_issues = []
        
        print("🔍 Aplicando técnicas de AstroSS...")
        
        # Ejecutar todas las técnicas
        techniques = [
            ("Software de Grabación", self.detect_recording_software),
            ("Tiempos de Modificación", self.check_modification_times),
            ("Checks In-Instance", self.in_instance_checks),
            ("Checks Out-of-Instance", self.out_of_instance_checks),
            ("JNativeHook", self.detect_jnativehook),
            ("Archivos Ejecutados y Borrados", self.detect_executed_deleted_files)
        ]
        
        for technique_name, technique_func in techniques:
            try:
                print(f"  🔍 {technique_name}...")
                issues = technique_func()
                all_issues.extend(issues)
                if issues:
                    print(f"    ✅ {len(issues)} detecciones")
            except Exception as e:
                print(f"    ⚠️ Error en {technique_name}: {e}")
        
        print(f"✅ Técnicas de AstroSS completadas - {len(all_issues)} detecciones totales")
        return all_issues

