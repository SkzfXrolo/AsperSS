"""
Analizador de conexiones activas de Minecraft
Detecta procesos ocultos, subprocesos e inyecciones relacionadas con Minecraft
"""
import psutil
import socket
import subprocess
import os
import ctypes
from ctypes import wintypes

class MinecraftConnectionAnalyzer:
    """Analiza conexiones y procesos relacionados con Minecraft"""
    
    def __init__(self):
        self.minecraft_username = None
        self.injection_issues = []
    
    def scan_minecraft_processes_and_injections(self):
        """Escanea procesos de Minecraft y detecta inyecciones/subprocesos ocultos"""
        issues = []
        
        try:
            # Buscar todos los procesos relacionados con Java/Minecraft
            minecraft_pids = []
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'ppid', 'connections']):
                try:
                    name = proc.info['name'].lower()
                    if name in ['javaw.exe', 'java.exe', 'minecraft.exe']:
                        minecraft_pids.append(proc.info['pid'])
                        
                        # Verificar cmdline para detectar hacks
                        cmdline = ' '.join(proc.info.get('cmdline', [])).lower()
                        if any(hack in cmdline for hack in ['-javaagent:', 'vape', 'entropy', 'inject']):
                            issues.append({
                                'tipo': 'java_injection',
                                'nombre': f"Proceso Java con parámetros sospechosos: {proc.info['name']}",
                                'ruta': proc.info.get('exe', 'N/A'),
                                'archivo': proc.info.get('exe', 'N/A'),
                                'alerta': 'CRITICAL',
                                'categoria': 'JAVA_INJECTION',
                                'pid': proc.info['pid'],
                                'cmdline': cmdline
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Buscar subprocesos hijos de procesos de Minecraft
            for pid in minecraft_pids:
                try:
                    parent = psutil.Process(pid)
                    children = parent.children(recursive=True)
                    
                    for child in children:
                        try:
                            child_name = child.name().lower()
                            child_exe = child.exe().lower() if child.exe() else ''
                            
                            # Detectar procesos sospechosos hijos
                            if any(hack in child_name or hack in child_exe for hack in ['inject', 'vape', 'entropy', 'ghost', 'bypass']):
                                issues.append({
                                    'tipo': 'subprocess_injection',
                                    'nombre': f"Subproceso sospechoso: {child_name}",
                                    'ruta': child_exe,
                                    'archivo': child_exe,
                                    'alerta': 'CRITICAL',
                                    'categoria': 'SUBPROCESS_INJECTION',
                                    'pid': child.pid,
                                    'parent_pid': pid
                                })
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Detectar DLLs inyectadas en procesos de Minecraft
            for pid in minecraft_pids:
                try:
                    proc = psutil.Process(pid)
                    memory_maps = proc.memory_maps()
                    
                    for mem_map in memory_maps:
                        dll_path = mem_map.path.lower()
                        dll_name = os.path.basename(dll_path)
                        
                        # Detectar DLLs sospechosas
                        suspicious_dlls = ['vape', 'entropy', 'inject', 'ghost', 'bypass', 'stealth']
                        if any(hack in dll_path for hack in suspicious_dlls):
                            # Verificar si está en ubicación no estándar
                            if 'system32' not in dll_path and 'syswow64' not in dll_path:
                                issues.append({
                                    'tipo': 'dll_injection',
                                    'nombre': f"DLL inyectada: {dll_name}",
                                    'ruta': os.path.dirname(dll_path),
                                    'archivo': dll_path,
                                    'alerta': 'CRITICAL',
                                    'categoria': 'DLL_INJECTION',
                                    'pid': pid
                                })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Detectar procesos ocultos relacionados con Minecraft
            self._detect_hidden_processes(issues)
            
            # Obtener username desde conexiones activas
            self.minecraft_username = self._extract_username_from_connections()
            
        except Exception as e:
            print(f"⚠️ Error escaneando procesos de Minecraft: {e}")
        
        return issues
    
    def _detect_hidden_processes(self, issues):
        """Detecta procesos ocultos que intentan evadir detección"""
        try:
            # Buscar procesos con nombres que intentan ocultarse
            hidden_patterns = [
                'svchost', 'services', 'dwm', 'csrss',  # Procesos del sistema comúnmente suplantados
            ]
            
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    name = proc.info['name'].lower()
                    exe = proc.info.get('exe', '').lower()
                    cmdline = ' '.join(proc.info.get('cmdline', [])).lower()
                    
                    # Verificar si un proceso del sistema tiene comportamiento sospechoso
                    if name in hidden_patterns:
                        # Verificar si tiene conexiones de red sospechosas
                        try:
                            connections = proc.connections()
                            for conn in connections:
                                if conn.status == 'ESTABLISHED':
                                    # Verificar si se conecta a puertos relacionados con Minecraft
                                    if conn.raddr and conn.raddr.port in [25565, 25566, 25567]:
                                        issues.append({
                                            'tipo': 'hidden_process',
                                            'nombre': f"Proceso oculto suplantando {name}",
                                            'ruta': exe,
                                            'archivo': exe,
                                            'alerta': 'CRITICAL',
                                            'categoria': 'HIDDEN_PROCESS',
                                            'pid': proc.info['pid']
                                        })
                        except:
                            pass
                        
                        # Verificar cmdline sospechoso
                        if any(hack in cmdline for hack in ['minecraft', 'java', 'vape', 'entropy']):
                            issues.append({
                                'tipo': 'hidden_process',
                                'nombre': f"Proceso oculto: {name} con cmdline sospechoso",
                                'ruta': exe,
                                'archivo': exe,
                                'alerta': 'CRITICAL',
                                'categoria': 'HIDDEN_PROCESS',
                                'pid': proc.info['pid']
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"⚠️ Error detectando procesos ocultos: {e}")
    
    def _extract_username_from_connections(self):
        """Extrae el username de Minecraft desde conexiones de red activas"""
        try:
            # Buscar procesos de Minecraft con conexiones activas
            for proc in psutil.process_iter(['pid', 'name', 'connections']):
                try:
                    name = proc.info['name'].lower()
                    if name not in ['javaw.exe', 'java.exe', 'minecraft.exe']:
                        continue
                    
                    connections = proc.info.get('connections', [])
                    for conn in connections:
                        if conn.status == 'ESTABLISHED' and conn.raddr:
                            # Intentar leer memoria del proceso para encontrar username
                            # Esto es más avanzado y requiere permisos elevados
                            username = self._read_username_from_memory(proc.info['pid'])
                            if username:
                                return username
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return None
        except Exception as e:
            print(f"⚠️ Error extrayendo username desde conexiones: {e}")
            return None
    
    def _read_username_from_memory(self, pid):
        """Intenta leer el username desde la memoria del proceso (requiere permisos elevados)"""
        try:
            # Usar Windows API para leer memoria del proceso
            PROCESS_VM_READ = 0x0010
            PROCESS_QUERY_INFORMATION = 0x0400
            
            kernel32 = ctypes.windll.kernel32
            process_handle = kernel32.OpenProcess(
                PROCESS_VM_READ | PROCESS_QUERY_INFORMATION,
                False,
                pid
            )
            
            if not process_handle:
                return None
            
            try:
                # Buscar patrones comunes de username en memoria
                # Los usernames de Minecraft suelen estar en formato específico
                # Esto es una implementación básica - se puede mejorar
                import re
                
                # Leer bloques de memoria (esto es simplificado)
                # En producción, necesitarías un análisis más profundo
                return None  # Por ahora retornar None, implementación avanzada requerida
            finally:
                kernel32.CloseHandle(process_handle)
        except Exception as e:
            # Si falla, no es crítico
            return None
    
    def detect_autoclicker_processes(self):
        """Detecta procesos de autoclicker relacionados con Minecraft"""
        issues = []
        
        try:
            autoclicker_keywords = [
                'autoclick', 'auto-click', 'clicker', 'ghostclick',
                'opautoclicker', 'autoclicker', 'rapidclick'
            ]
            
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    name = proc.info['name'].lower()
                    exe = proc.info.get('exe', '').lower()
                    cmdline = ' '.join(proc.info.get('cmdline', [])).lower()
                    
                    # Verificar si es un autoclicker
                    if any(keyword in name or keyword in exe or keyword in cmdline for keyword in autoclicker_keywords):
                        # Verificar si tiene conexiones o está relacionado con Minecraft
                        try:
                            connections = proc.connections()
                            has_minecraft_connection = False
                            
                            for conn in connections:
                                if conn.status == 'ESTABLISHED':
                                    # Verificar si se conecta a puertos comunes de Minecraft
                                    if conn.raddr and conn.raddr.port in [25565, 25566, 25567]:
                                        has_minecraft_connection = True
                                        break
                            
                            if has_minecraft_connection or 'minecraft' in cmdline:
                                issues.append({
                                    'tipo': 'autoclicker',
                                    'nombre': f"Autoclicker detectado: {name}",
                                    'ruta': exe,
                                    'archivo': exe,
                                    'alerta': 'CRITICAL',
                                    'categoria': 'AUTOCLICKER',
                                    'pid': proc.info['pid']
                                })
                        except:
                            # Si no puede verificar conexiones, aún reportar el proceso
                            issues.append({
                                'tipo': 'autoclicker',
                                'nombre': f"Autoclicker detectado: {name}",
                                'ruta': exe,
                                'archivo': exe,
                                'alerta': 'SOSPECHOSO',
                                'categoria': 'AUTOCLICKER',
                                'pid': proc.info['pid']
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"⚠️ Error detectando autoclickers: {e}")
        
        return issues

