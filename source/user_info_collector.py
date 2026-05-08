"""
Módulo para recopilar información del usuario:
- País por IP
- Username de Minecraft
- Historial de bans previos
"""
import os
import json
import requests
import socket
import platform
from pathlib import Path

class UserInfoCollector:
    """Recopila información del usuario para el escaneo"""
    
    def __init__(self):
        self.minecraft_username = None
        self.country = None
        self.ip_address = None
        self.previous_bans = []
    
    def get_ip_address(self):
        """Obtiene la IP pública del usuario"""
        try:
            # Intentar obtener IP pública usando servicios gratuitos
            services = [
                'https://api.ipify.org?format=json',
                'https://ifconfig.me/ip',
                'https://icanhazip.com'
            ]
            
            for service in services:
                try:
                    response = requests.get(service, timeout=3)
                    if response.status_code == 200:
                        if 'json' in service:
                            self.ip_address = response.json().get('ip', '').strip()
                        else:
                            self.ip_address = response.text.strip()
                        
                        if self.ip_address:
                            return self.ip_address
                except:
                    continue
            
            # Fallback: obtener IP local
            hostname = socket.gethostname()
            self.ip_address = socket.gethostbyname(hostname)
            return self.ip_address
        except Exception as e:
            print(f"⚠️ Error obteniendo IP: {e}")
            return None
    
    def get_country_from_ip(self, ip_address=None):
        """Obtiene el país basado en la IP"""
        if not ip_address:
            ip_address = self.get_ip_address()
        
        if not ip_address:
            return None
        
        try:
            # Usar servicio gratuito para geolocalización
            response = requests.get(
                f'http://ip-api.com/json/{ip_address}?fields=status,country,countryCode',
                timeout=3
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    self.country = data.get('country', 'Unknown')
                    return self.country
        except Exception as e:
            print(f"⚠️ Error obteniendo país: {e}")
        
        return None
    
    def get_minecraft_username_from_connections(self):
        """Obtiene el username de Minecraft desde conexiones de red activas"""
        try:
            import psutil
            import socket
            
            # Buscar procesos de Minecraft/Java activos
            minecraft_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'connections']):
                try:
                    name = proc.info['name'].lower()
                    if name in ['javaw.exe', 'java.exe', 'minecraft.exe']:
                        minecraft_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Buscar conexiones de red activas relacionadas con Minecraft
            for proc in minecraft_processes:
                try:
                    connections = proc.info.get('connections', [])
                    for conn in connections:
                        if conn.status == 'ESTABLISHED' and conn.raddr:
                            # Intentar obtener información de la conexión
                            # Los servidores de Minecraft suelen estar en puertos específicos
                            if conn.raddr.port in [25565, 25566, 25567, 25568]:  # Puertos comunes de Minecraft
                                # Aquí podríamos hacer un análisis más profundo de la conexión
                                # Por ahora, intentamos obtener el username de otras formas
                                pass
                except:
                    continue
            
            return None
        except Exception as e:
            print(f"⚠️ Error obteniendo username desde conexiones: {e}")
            return None
    
    def get_minecraft_username(self):
        """Obtiene el username de Minecraft. Orden de prioridad:
        1. --username del proceso Java en ejecución (100% fiable, todos los launchers lo pasan)
        2. launcher_accounts.json → cuenta activa (cuenta Microsoft moderna)
        3. launcher_profiles.json → authenticationDatabase (cuentas legacy/Mojang)
        4. usercache.json → entrada más reciente (puede ser de otro jugador, evitar si es posible)
        """
        # Prioridad máxima: leer --username del proceso Java activo
        try:
            mc_info = self.get_minecraft_active_info()
            if mc_info.get('mc_username'):
                self.minecraft_username = mc_info['mc_username']
                return self.minecraft_username
        except Exception:
            pass

        # Si no hay proceso corriendo, buscar en archivos del launcher
        try:
            # Rutas comunes donde se guarda el username de Minecraft
            minecraft_paths = [
                os.path.expanduser("~\\AppData\\Roaming\\.minecraft"),
                os.path.expanduser("~\\AppData\\Local\\.minecraft"),
            ]
            
            # Archivos donde puede estar el username
            config_files = [
                'launcher_profiles.json',
                'launcher_accounts.json',
                'usercache.json',
                'options.txt'
            ]
            
            for minecraft_path in minecraft_paths:
                if not os.path.exists(minecraft_path):
                    continue
                
                # Buscar en launcher_profiles.json — authenticationDatabase tiene el username real
                # NOTA: profiles[].name es el nombre del perfil del launcher (ej. "1.21.8 Fabric"),
                #        NO el nombre de la cuenta de Minecraft. Usar authenticationDatabase.
                launcher_profiles = os.path.join(minecraft_path, 'launcher_profiles.json')
                if os.path.exists(launcher_profiles):
                    try:
                        with open(launcher_profiles, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            auth_db = data.get('authenticationDatabase', {})
                            for entry in auth_db.values():
                                username = entry.get('displayName', '')
                                if username and len(username) >= 3:
                                    self.minecraft_username = username
                                    return username
                    except:
                        pass
                
                # Buscar en launcher_accounts.json
                launcher_accounts = os.path.join(minecraft_path, 'launcher_accounts.json')
                if os.path.exists(launcher_accounts):
                    try:
                        with open(launcher_accounts, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        if 'accounts' in data:
                            # Priorizar la cuenta activa si está indicada
                            active_id = data.get('activeAccountLocalId', '')
                            accounts = data['accounts']
                            ordered = []
                            if active_id and active_id in accounts:
                                ordered.append(accounts[active_id])
                            ordered.extend(v for k, v in accounts.items() if k != active_id)

                            for account_data in ordered:
                                # Cuentas Microsoft modernas: minecraftProfile.name
                                mc_profile = account_data.get('minecraftProfile', {})
                                username = mc_profile.get('name', '') if mc_profile else ''
                                # Fallback: campo username directo (cuentas legacy/Mojang)
                                if not username:
                                    username = account_data.get('username', '')
                                if username and len(username) >= 3:
                                    self.minecraft_username = username
                                    return username
                    except:
                        pass
                
                # NOTE: usercache.json is intentionally skipped — it caches names of OTHER
                # players seen on servers, not the logged-in user. Using it causes the bug
                # where a random player's name appears instead of the real account holder.

                # Last resort: scan MC logs for login/session lines that identify the account holder
                logs_path = os.path.join(minecraft_path, 'logs')
                if os.path.exists(logs_path):
                    try:
                        import re
                        log_files = sorted(
                            [f for f in os.listdir(logs_path) if f.endswith('.log') or f == 'latest.log'],
                            key=lambda x: os.path.getmtime(os.path.join(logs_path, x)),
                            reverse=True
                        )
                        for log_file in log_files[:3]:
                            log_path = os.path.join(logs_path, log_file)
                            try:
                                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                # These patterns only appear once per session and identify the logged-in account:
                                # "Setting user: <name>" (vanilla/Forge/Fabric)
                                # "Logging in with <name>" (some launchers)
                                for pattern in [
                                    r'Setting user:\s+([A-Za-z0-9_]{3,16})',
                                    r'Logging in with\s+([A-Za-z0-9_]{3,16})',
                                    r'\[(?:Client thread|main)/INFO\].*?Hello,\s+([A-Za-z0-9_]{3,16})',
                                ]:
                                    m = re.search(pattern, content)
                                    if m:
                                        self.minecraft_username = m.group(1)
                                        return self.minecraft_username
                            except:
                                continue
                    except:
                        pass
            
            return None
        except Exception as e:
            print(f"⚠️ Error obteniendo username de Minecraft: {e}")
            return None
    
    def get_minecraft_active_info(self):
        """Detects running Minecraft version, launcher type, loaded mods/agents, and logged-in username."""
        result = {
            'mc_running': False,
            'mc_version': None,
            'mc_launcher': None,
            'mc_mods': [],
            'java_agents': [],
            'mc_username': None,  # username from --username flag (most reliable source)
        }
        try:
            import psutil, re
            for proc in psutil.process_iter(['name', 'cmdline', 'exe']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    cmdline = proc.info.get('cmdline') or []
                    cmd_str = ' '.join(str(c) for c in cmdline)
                    cmd_lower = cmd_str.lower()

                    is_java = name in ('java.exe', 'javaw.exe', 'java', 'javaw')
                    if not is_java:
                        continue
                    if 'minecraft' not in cmd_lower and 'net.minecraft' not in cmd_lower:
                        continue

                    result['mc_running'] = True

                    # --username is passed by ALL launchers (vanilla, Lunar, Badlion, Forge…)
                    # Use original cmd_str (not lowercased) to preserve casing
                    um = re.search(r'--username\s+([A-Za-z0-9_]{3,16})', cmd_str)
                    if um:
                        result['mc_username'] = um.group(1)

                    vm = re.search(r'--version\s+([^\s]+)', cmd_lower)
                    if vm:
                        result['mc_version'] = vm.group(1)

                    for launcher, keyword in [
                        ('Lunar Client', 'lunarclient'),
                        ('Badlion Client', 'badlion'),
                        ('Feather Client', 'feather'),
                        ('Forge', 'minecraftforge'),
                        ('Fabric', 'fabricmc'),
                        ('Quilt', 'quiltmc'),
                        ('OptiFine', 'optifine'),
                        ('Official Launcher', 'net.minecraft.client.main'),
                    ]:
                        if keyword in cmd_lower:
                            result['mc_launcher'] = launcher
                            break

                    agents = re.findall(r'-javaagent:([^\s]+)', cmd_str)
                    result['java_agents'] = agents

                    game_dir_m = re.search(r'--gameDir\s+([^\s]+)', cmd_str)
                    if game_dir_m:
                        mods_path = os.path.join(game_dir_m.group(1), 'mods')
                        if os.path.isdir(mods_path):
                            result['mc_mods'] = [
                                f for f in os.listdir(mods_path)
                                if f.endswith(('.jar', '.zip'))
                            ][:50]

                    break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"⚠️ Error detectando MC activo: {e}")
        return result

    def collect_all_info(self):
        """Recopila toda la información del usuario"""
        mc_info = self.get_minecraft_active_info()

        # If MC is running, we already have the username from --username flag;
        # pass it directly so get_minecraft_username() doesn't scan the process again.
        if mc_info.get('mc_username'):
            self.minecraft_username = mc_info['mc_username']
            mc_username = mc_info['mc_username']
        else:
            mc_username = self.get_minecraft_username()

        # Filtro #46 — detección de Windows Server. Si el host es Server,
        # marcamos `os` con sufijo "Server" para que el panel pueda
        # bajar peso de heurísticas que asumen entorno desktop.
        os_label = platform.system()
        try:
            edition = platform.win32_edition() if hasattr(platform, 'win32_edition') else None
            if edition and 'server' in str(edition).lower():
                os_label = f'{os_label} Server'
        except Exception:
            pass

        info = {
            'ip_address': self.get_ip_address(),
            'country': self.get_country_from_ip(),
            'minecraft_username': mc_username,
            'os': os_label,
            'os_version': platform.version(),
            'mc_running': mc_info['mc_running'],
            'mc_version': mc_info['mc_version'],
            'mc_launcher': mc_info['mc_launcher'],
            'mc_mods': mc_info['mc_mods'],
            'java_agents': mc_info['java_agents'],
        }

        return info

