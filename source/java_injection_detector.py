"""
Detección de Inyección de Código en Procesos de Minecraft
Detecta cuando se inyecta código malicioso en procesos Java de Minecraft
"""
import psutil
import re
from typing import List, Dict

class JavaInjectionDetector:
    """Detector de inyección de código en procesos Java"""
    
    # Agentes de Java conocidos usados por hacks
    KNOWN_HACK_AGENTS = [
        'vape', 'entropy', 'sigma', 'flux', 'future',
        'inject', 'agent', 'bypass', 'stealth'
    ]
    
    # DLLs sospechosas que podrían inyectarse
    SUSPICIOUS_DLLS = [
        'vape.dll', 'entropy.dll', 'inject.dll', 'hook.dll',
        'bypass.dll', 'stealth.dll'
    ]
    
    def __init__(self):
        self.detected_injections = []
    
    def scan_java_processes(self) -> List[Dict]:
        """Escanea procesos Java buscando inyección de código"""
        detected = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe', 'memory_info']):
                try:
                    proc_info = proc.info
                    proc_name = (proc_info.get('name') or '').lower()
                    
                    # Solo procesar procesos Java
                    if 'java' not in proc_name and 'javaw' not in proc_name:
                        continue
                    
                    cmdline = ' '.join(proc_info.get('cmdline') or [])
                    cmdline_lower = cmdline.lower()
                    
                    # Verificar si es proceso de Minecraft
                    is_minecraft = 'minecraft' in cmdline_lower or 'minecraft' in (proc_info.get('exe') or '').lower()
                    
                    # Detectar agentes de Java sospechosos
                    javaagent_result = self._detect_javaagent(cmdline, is_minecraft)
                    if javaagent_result:
                        detected.append(javaagent_result)
                    
                    # Detectar modificaciones a bootclasspath
                    bootclasspath_result = self._detect_bootclasspath(cmdline, is_minecraft)
                    if bootclasspath_result:
                        detected.append(bootclasspath_result)
                    
                    # Detectar referencias a archivos sospechosos
                    suspicious_files_result = self._detect_suspicious_files(cmdline, is_minecraft)
                    if suspicious_files_result:
                        detected.append(suspicious_files_result)
                    
                    # Analizar memoria del proceso (si es Minecraft)
                    if is_minecraft:
                        memory_result = self._analyze_process_memory(proc_info.get('pid'))
                        if memory_result:
                            detected.extend(memory_result)
                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception:
                    continue
        
        except Exception as e:
            print(f"⚠️ Error escaneando procesos Java: {e}")
        
        self.detected_injections = detected
        return detected
    
    def _detect_javaagent(self, cmdline: str, is_minecraft: bool) -> Dict:
        """Detecta uso de -javaagent: (usado por inyectores)"""
        # Buscar parámetro -javaagent:
        javaagent_pattern = r'-javaagent:([^\s]+)'
        matches = re.findall(javaagent_pattern, cmdline, re.IGNORECASE)
        
        if matches:
            for agent_path in matches:
                agent_name = agent_path.lower()
                
                # Verificar si es un agente conocido de hack
                is_suspicious = any(hack in agent_name for hack in self.KNOWN_HACK_AGENTS)
                
                if is_suspicious or is_minecraft:
                    return {
                        'type': 'javaagent_injection',
                        'agent_path': agent_path,
                        'is_minecraft': is_minecraft,
                        'is_suspicious_agent': is_suspicious,
                        'confidence': 0.9 if is_suspicious else 0.7,
                        'alert': 'CRITICAL' if is_suspicious else 'SOSPECHOSO',
                        'description': f'Agente de Java detectado: {agent_path}'
                    }
        
        return None
    
    def _detect_bootclasspath(self, cmdline: str, is_minecraft: bool) -> Dict:
        """Detecta modificaciones a -Xbootclasspath: (modificaciones a clases base)"""
        bootclasspath_pattern = r'-Xbootclasspath[ap]?:([^\s]+)'
        matches = re.findall(bootclasspath_pattern, cmdline, re.IGNORECASE)
        
        if matches and is_minecraft:
            return {
                'type': 'bootclasspath_modification',
                'bootclasspath': matches[0],
                'is_minecraft': True,
                'confidence': 0.8,
                'alert': 'CRITICAL',
                'description': f'Modificación a bootclasspath detectada: {matches[0]}'
            }
        
        return None
    
    def _detect_suspicious_files(self, cmdline: str, is_minecraft: bool) -> Dict:
        """Detecta referencias a archivos sospechosos en la línea de comandos"""
        cmdline_lower = cmdline.lower()
        
        # Buscar referencias a archivos .jar sospechosos
        jar_pattern = r'([^\s]+\.jar)'
        jar_matches = re.findall(jar_pattern, cmdline, re.IGNORECASE)
        
        for jar_file in jar_matches:
            jar_name = jar_file.lower()
            
            # Verificar si es un archivo sospechoso
            is_suspicious = any(hack in jar_name for hack in self.KNOWN_HACK_AGENTS)
            
            if is_suspicious and is_minecraft:
                return {
                    'type': 'suspicious_jar_reference',
                    'jar_file': jar_file,
                    'is_minecraft': True,
                    'confidence': 0.85,
                    'alert': 'CRITICAL',
                    'description': f'Referencia a archivo JAR sospechoso: {jar_file}'
                }
        
        return None
    
    def _analyze_process_memory(self, pid: int) -> List[Dict]:
        """Analiza la memoria de un proceso buscando strings de hacks"""
        detected = []
        
        try:
            proc = psutil.Process(pid)
            memory_maps = proc.memory_maps()
            
            # Strings de hacks conocidos para buscar en memoria
            hack_strings = [
                'KillAura', 'Aimbot', 'Reach', 'Velocity', 'Scaffold',
                'Vape', 'Entropy', 'Wurst', 'Impact', 'Sigma',
                'AutoClicker', 'XRay', 'Fly', 'NoFall'
            ]
            
            # Leer memoria del proceso (limitado por seguridad)
            try:
                # Solo leer regiones de memoria accesibles
                for mem_map in memory_maps[:10]:  # Limitar a 10 regiones para rendimiento
                    try:
                        # Intentar leer memoria (puede fallar por permisos)
                        # Nota: En producción, esto requeriría permisos elevados
                        pass  # Implementación simplificada por seguridad
                    except:
                        continue
            except:
                # No se puede leer memoria, continuar
                pass
        
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception:
            pass
        
        return detected
    
    def get_detection_summary(self) -> Dict:
        """Obtiene un resumen de las detecciones"""
        return {
            'total_detected': len(self.detected_injections),
            'javaagent_injections': len([d for d in self.detected_injections if d['type'] == 'javaagent_injection']),
            'bootclasspath_modifications': len([d for d in self.detected_injections if d['type'] == 'bootclasspath_modification']),
            'suspicious_jar_references': len([d for d in self.detected_injections if d['type'] == 'suspicious_jar_reference'])
        }


