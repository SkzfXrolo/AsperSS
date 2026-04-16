"""
Detección de Autoclickers Activos en Tiempo Real
Detecta procesos de autoclickers ejecutándose durante el escaneo
"""
import psutil
import re
from typing import List, Dict

class AutoclickerDetector:
    """Detector de autoclickers activos"""
    
    # Nombres conocidos de autoclickers
    AUTOCLICKER_NAMES = [
        'autoclicker', 'auto-clicker', 'auto_clicker', 'ac.exe', 'ac.jar',
        'op autoclicker', 'gs autoclicker', 'cps autoclicker',
        'fastclick', 'rapidclick', 'clickbot', 'clicker',
        'tinytools', 'tiny-tools', 'tiny_tools'
    ]
    
    # Procesos sospechosos relacionados con automatización
    SUSPICIOUS_PROCESSES = [
        'autohotkey', 'ahk', 'autoit', 'macro', 'script',
        'click', 'automation', 'bot'
    ]
    
    def __init__(self):
        self.detected_processes = []
    
    def scan_running_processes(self) -> List[Dict]:
        """Escanea procesos activos buscando autoclickers"""
        detected = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'create_time']):
                try:
                    proc_info = proc.info
                    proc_name = (proc_info.get('name') or '').lower()
                    proc_exe = (proc_info.get('exe') or '').lower()
                    proc_cmdline = ' '.join(proc_info.get('cmdline') or [])
                    
                    # Verificar nombres conocidos
                    if self._matches_autoclicker_name(proc_name, proc_exe):
                        detected.append({
                            'type': 'autoclicker_process',
                            'name': proc_info.get('name', 'Unknown'),
                            'pid': proc_info.get('pid'),
                            'exe': proc_info.get('exe', ''),
                            'cmdline': proc_cmdline,
                            'confidence': 0.9,
                            'alert': 'CRITICAL'
                        })
                    
                    # Verificar procesos sospechosos
                    elif self._is_suspicious_process(proc_name, proc_exe, proc_cmdline):
                        detected.append({
                            'type': 'suspicious_automation',
                            'name': proc_info.get('name', 'Unknown'),
                            'pid': proc_info.get('pid'),
                            'exe': proc_info.get('exe', ''),
                            'cmdline': proc_cmdline,
                            'confidence': 0.6,
                            'alert': 'SOSPECHOSO'
                        })
                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    continue
        
        except Exception as e:
            print(f"⚠️ Error escaneando procesos: {e}")
        
        self.detected_processes = detected
        return detected
    
    def _matches_autoclicker_name(self, name: str, exe: str) -> bool:
        """Verifica si un nombre de proceso coincide con autoclickers conocidos"""
        combined = f"{name} {exe}".lower()
        
        for pattern in self.AUTOCLICKER_NAMES:
            if pattern.lower() in combined:
                return True
        
        return False
    
    def _is_suspicious_process(self, name: str, exe: str, cmdline: str) -> bool:
        """Verifica si un proceso es sospechoso de automatización"""
        combined = f"{name} {exe} {cmdline}".lower()
        
        # Buscar patrones de automatización
        suspicious_patterns = [
            r'click.*automation',
            r'auto.*click',
            r'macro.*script',
            r'bot.*click',
            r'cps.*click'
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, combined):
                return True
        
        # Verificar procesos conocidos de automatización
        for proc in self.SUSPICIOUS_PROCESSES:
            if proc in combined:
                return True
        
        return False
    
    def check_minecraft_processes(self) -> List[Dict]:
        """Verifica procesos de Minecraft buscando inyección de autoclickers"""
        detected = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_info = proc.info
                    proc_name = (proc_info.get('name') or '').lower()
                    proc_cmdline = ' '.join(proc_info.get('cmdline') or [])
                    
                    # Buscar procesos Java relacionados con Minecraft
                    if 'java' in proc_name or 'javaw' in proc_name:
                        if 'minecraft' in proc_cmdline.lower():
                            # Verificar si hay parámetros sospechosos
                            if self._has_suspicious_java_args(proc_cmdline):
                                detected.append({
                                    'type': 'minecraft_injection',
                                    'name': proc_info.get('name', 'Unknown'),
                                    'pid': proc_info.get('pid'),
                                    'cmdline': proc_cmdline,
                                    'confidence': 0.8,
                                    'alert': 'CRITICAL'
                                })
                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    continue
        
        except Exception as e:
            print(f"⚠️ Error verificando procesos de Minecraft: {e}")
        
        return detected
    
    def _has_suspicious_java_args(self, cmdline: str) -> bool:
        """Verifica si la línea de comandos de Java tiene argumentos sospechosos"""
        suspicious_args = [
            '-javaagent:',
            'autoclicker',
            'clicker',
            'macro',
            'bot'
        ]
        
        cmdline_lower = cmdline.lower()
        for arg in suspicious_args:
            if arg in cmdline_lower:
                return True
        
        return False
    
    def get_detection_summary(self) -> Dict:
        """Obtiene un resumen de las detecciones"""
        return {
            'total_detected': len(self.detected_processes),
            'autoclickers': len([d for d in self.detected_processes if d['type'] == 'autoclicker_process']),
            'suspicious': len([d for d in self.detected_processes if d['type'] == 'suspicious_automation']),
            'minecraft_injections': len([d for d in self.detected_processes if d['type'] == 'minecraft_injection'])
        }


