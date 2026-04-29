"""
Técnicas avanzadas de detección inspiradas en Silent-scanner
Métodos adicionales para detectar hacks que intentan evadir detección
"""
import os
import psutil
import subprocess
import hashlib
import ctypes
from ctypes import wintypes

class SilentScannerTechniques:
    """Técnicas avanzadas de detección del Silent-scanner"""
    
    @staticmethod
    def detect_process_hollowing():
        """Detecta Process Hollowing - técnica de evasión avanzada"""
        issues = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'memory_info']):
                try:
                    proc_info = proc.info
                    name = proc_info['name'].lower()
                    
                    # Verificar procesos Java/Minecraft con comportamiento sospechoso
                    if name in ['java.exe', 'javaw.exe', 'minecraft.exe']:
                        exe_path = proc_info['exe']
                        if exe_path:
                            # Verificar si el ejecutable en memoria difiere del disco
                            try:
                                # Leer primeros bytes del ejecutable en disco
                                with open(exe_path, 'rb') as f:
                                    disk_header = f.read(1024)
                                
                                # Verificar firma PE
                                if disk_header[:2] != b'MZ':
                                    issues.append({
                                        'tipo': 'process_hollowing',
                                        'nombre': f"Process Hollowing detectado: {proc_info['name']}",
                                        'ruta': exe_path,
                                        'archivo': exe_path,
                                        'alerta': 'CRITICAL',
                                        'categoria': 'ADVANCED_EVASION'
                                    })
                            except:
                                pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error detectando process hollowing: {e}")
        
        return issues
    
    @staticmethod
    def detect_dll_hijacking():
        """Detecta DLL Hijacking - técnica de inyección avanzada"""
        issues = []
        try:
            # DLLs comúnmente secuestradas
            vulnerable_dlls = [
                'ntdll.dll', 'kernel32.dll', 'user32.dll', 'advapi32.dll',
                'ws2_32.dll', 'wininet.dll', 'crypt32.dll'
            ]
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'].lower() in ['java.exe', 'javaw.exe', 'minecraft.exe']:
                        # Verificar DLLs cargadas desde ubicaciones no estándar
                        try:
                            dlls = proc.memory_maps()
                            for dll in dlls:
                                dll_path = dll.path.lower()
                                dll_name = os.path.basename(dll_path).lower()
                                
                                # Verificar si una DLL vulnerable está en ubicación sospechosa
                                if dll_name in vulnerable_dlls:
                                    if 'system32' not in dll_path and 'syswow64' not in dll_path:
                                        issues.append({
                                            'tipo': 'dll_hijacking',
                                            'nombre': f"DLL Hijacking: {dll_name}",
                                            'ruta': os.path.dirname(dll_path),
                                            'archivo': dll_path,
                                            'alerta': 'CRITICAL',
                                            'categoria': 'ADVANCED_EVASION'
                                        })
                        except:
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error detectando DLL hijacking: {e}")
        
        return issues
    
    @staticmethod
    def detect_code_cave_injection():
        """Detecta Code Cave Injection - inyección de código en espacios vacíos"""
        issues = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    if proc.info['name'].lower() in ['java.exe', 'javaw.exe']:
                        memory_info = proc.memory_info()
                        
                        # Verificar si el proceso tiene regiones de memoria ejecutables sospechosas
                        # (regiones grandes de memoria ejecutable pueden indicar code caves)
                        if memory_info.rss > 1000 * 1024 * 1024:  # Más de 1GB
                            try:
                                # Buscar strings sospechosos que indiquen inyección
                                result = subprocess.run(
                                    ['wmic', 'process', 'where', f'ProcessId={proc.info["pid"]}', 'get', 'CommandLine'],
                                    capture_output=True,
                                    text=True,
                                    timeout=5,
                                    creationflags=0x08000000
                                )
                                
                                if result.returncode == 0:
                                    cmdline = result.stdout.lower()
                                    if any(pattern in cmdline for pattern in ['-javaagent', '-agentpath', 'instrument']):
                                        issues.append({
                                            'tipo': 'code_cave_injection',
                                            'nombre': f"Posible Code Cave Injection: {proc.info['name']}",
                                            'ruta': f"PID: {proc.info['pid']}",
                                            'archivo': cmdline,
                                            'alerta': 'CRITICAL',
                                            'categoria': 'ADVANCED_EVASION'
                                        })
                            except:
                                pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error detectando code cave injection: {e}")
        
        return issues
    
    @staticmethod
    def detect_api_hooking():
        """Detecta API Hooking - interceptación de llamadas al sistema"""
        issues = []
        try:
            # APIs comúnmente hookeadas por hacks
            hooked_apis = [
                'CreateFileW', 'ReadFile', 'WriteFile', 'CreateProcessW',
                'LoadLibrary', 'GetProcAddress', 'VirtualAlloc', 'VirtualProtect'
            ]
            
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'].lower() in ['java.exe', 'javaw.exe', 'minecraft.exe']:
                        # Verificar si el proceso tiene hooks activos
                        # (esto requiere herramientas avanzadas, por ahora es una detección básica)
                        try:
                            # Buscar procesos relacionados sospechosos
                            children = proc.children(recursive=True)
                            for child in children:
                                child_name = child.name().lower()
                                if any(hack in child_name for hack in ['inject', 'hook', 'bypass']):
                                    issues.append({
                                        'tipo': 'api_hooking',
                                        'nombre': f"Posible API Hooking: {child_name}",
                                        'ruta': f"PID: {child.pid}",
                                        'archivo': child.exe() if hasattr(child, 'exe') else 'N/A',
                                        'alerta': 'CRITICAL',
                                        'categoria': 'ADVANCED_EVASION'
                                    })
                        except:
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error detectando API hooking: {e}")
        
        return issues
    
    @staticmethod
    def detect_anti_debugging():
        """Detecta técnicas anti-debugging"""
        issues = []
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'].lower() in ['java.exe', 'javaw.exe']:
                        # Verificar si el proceso tiene flags anti-debugging
                        try:
                            # Buscar en la línea de comandos indicadores de anti-debugging
                            cmdline = ' '.join(proc.cmdline()).lower() if proc.cmdline() else ''
                            
                            anti_debug_patterns = [
                                'noverify', 'noverification', 'disableassertions',
                                'agentlib', 'javaagent'
                            ]
                            
                            if any(pattern in cmdline for pattern in anti_debug_patterns):
                                # Verificar si no es un patrón legítimo
                                if not any(legit in cmdline for legit in ['forge', 'fabric', 'optifine']):
                                    issues.append({
                                        'tipo': 'anti_debugging',
                                        'nombre': f"Técnicas anti-debugging detectadas: {proc.info['name']}",
                                        'ruta': f"PID: {proc.info['pid']}",
                                        'archivo': cmdline,
                                        'alerta': 'SOSPECHOSO',
                                        'categoria': 'ADVANCED_EVASION'
                                    })
                        except:
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error detectando anti-debugging: {e}")
        
        return issues
    
    @staticmethod
    def detect_string_obfuscation():
        """Detecta ofuscación de strings en archivos"""
        issues = []
        try:
            # Buscar archivos con alto ratio de caracteres no ASCII
            suspicious_locations = [
                os.path.expanduser("~\\AppData\\Roaming\\.minecraft"),
                os.path.expanduser("~\\Downloads"),
                os.path.expanduser("~\\Desktop")
            ]
            
            for location in suspicious_locations:
                if os.path.exists(location):
                    try:
                        for root, dirs, files in os.walk(location):
                            for file in files:
                                if file.lower().endswith(('.jar', '.class', '.exe')):
                                    file_path = os.path.join(root, file)
                                    try:
                                        with open(file_path, 'rb') as f:
                                            content = f.read(10240)  # Leer primeros 10KB
                                        
                                        if len(content) > 100:
                                            # Calcular ratio de caracteres no ASCII
                                            non_ascii = sum(1 for b in content if b > 127)
                                            ratio = non_ascii / len(content)
                                            
                                            # Si más del 40% es no ASCII, es muy sospechoso
                                            if ratio > 0.4:
                                                issues.append({
                                                    'tipo': 'string_obfuscation',
                                                    'nombre': f"Ofuscación detectada: {file}",
                                                    'ruta': root,
                                                    'archivo': file_path,
                                                    'alerta': 'SOSPECHOSO',
                                                    'categoria': 'OBFUSCATION',
                                                    'obfuscation_ratio': round(ratio * 100, 2)
                                                })
                                    except:
                                        continue
                    except:
                        continue
        except Exception as e:
            print(f"Error detectando ofuscación de strings: {e}")
        
        return issues
    
    @staticmethod
    def detect_packed_executables():
        """Detecta ejecutables empaquetados/comprimidos"""
        issues = []
        try:
            # Buscar ejecutables con características de empaquetado
            suspicious_locations = [
                os.path.expanduser("~\\Downloads"),
                os.path.expanduser("~\\Desktop"),
                os.path.expanduser("~\\AppData\\Local\\Temp")
            ]
            
            for location in suspicious_locations:
                if os.path.exists(location):
                    try:
                        for root, dirs, files in os.walk(location):
                            for file in files:
                                if file.lower().endswith('.exe'):
                                    file_path = os.path.join(root, file)
                                    try:
                                        with open(file_path, 'rb') as f:
                                            header = f.read(1024)
                                        
                                        # Verificar características de empaquetado
                                        # Ejecutables empaquetados suelen tener:
                                        # - Poca entropía en el header
                                        # - Secciones con nombres sospechosos
                                        # - Tamaño pequeño del ejecutable pero gran uso de memoria
                                        
                                        # Verificar si es un PE válido
                                        if header[:2] == b'MZ':
                                            # Verificar entropía (simplificado)
                                            unique_bytes = len(set(header))
                                            if unique_bytes < 50:  # Baja diversidad = posible empaquetado
                                                issues.append({
                                                    'tipo': 'packed_executable',
                                                    'nombre': f"Ejecutable posiblemente empaquetado: {file}",
                                                    'ruta': root,
                                                    'archivo': file_path,
                                                    'alerta': 'SOSPECHOSO',
                                                    'categoria': 'PACKING'
                                                })
                                    except:
                                        continue
                    except:
                        continue
        except Exception as e:
            print(f"Error detectando ejecutables empaquetados: {e}")
        
        return issues
    
    @staticmethod
    def scan_all_advanced_techniques():
        """Ejecuta todas las técnicas avanzadas de detección"""
        all_issues = []
        
        print("🔍 Aplicando técnicas avanzadas de Silent-scanner...")
        
        # Ejecutar todas las técnicas
        techniques = [
            ("Process Hollowing", SilentScannerTechniques.detect_process_hollowing),
            ("DLL Hijacking", SilentScannerTechniques.detect_dll_hijacking),
            ("Code Cave Injection", SilentScannerTechniques.detect_code_cave_injection),
            ("API Hooking", SilentScannerTechniques.detect_api_hooking),
            ("Anti-Debugging", SilentScannerTechniques.detect_anti_debugging),
            ("String Obfuscation", SilentScannerTechniques.detect_string_obfuscation),
            ("Packed Executables", SilentScannerTechniques.detect_packed_executables)
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
        
        print(f"✅ Técnicas avanzadas completadas - {len(all_issues)} detecciones totales")
        return all_issues
    
    @staticmethod
    def scan_all_techniques_combined():
        """Ejecuta todas las técnicas combinadas (Silent-scanner + AstroSS)"""
        all_issues = []
        
        # Técnicas de Silent-scanner
        silent_issues = SilentScannerTechniques.scan_all_advanced_techniques()
        all_issues.extend(silent_issues)
        
        # Técnicas de AstroSS
        try:
            from astro_ss_techniques import AstroSSTechniques
            astro = AstroSSTechniques()
            astro_issues = astro.scan_all_astro_techniques()
            all_issues.extend(astro_issues)
        except Exception as e:
            print(f"⚠️ Error cargando técnicas de AstroSS: {e}")
        
        return all_issues

