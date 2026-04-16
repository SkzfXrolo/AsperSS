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
        """Obtiene el username de Minecraft desde archivos locales Y conexiones activas"""
        # Primero intentar desde conexiones activas (más confiable)
        username_from_conn = self.get_minecraft_username_from_connections()
        if username_from_conn:
            return username_from_conn
        
        # Si no se encuentra, buscar en archivos
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
                
                # Buscar en launcher_profiles.json
                launcher_profiles = os.path.join(minecraft_path, 'launcher_profiles.json')
                if os.path.exists(launcher_profiles):
                    try:
                        with open(launcher_profiles, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                            # Buscar en profiles
                            if 'profiles' in data:
                                for profile_id, profile_data in data['profiles'].items():
                                    if 'name' in profile_data:
                                        username = profile_data['name']
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
                            
                            # Buscar en accounts
                            if 'accounts' in data:
                                for account_id, account_data in data['accounts'].items():
                                    if 'username' in account_data:
                                        username = account_data['username']
                                        if username and len(username) >= 3:
                                            self.minecraft_username = username
                                            return username
                    except:
                        pass
                
                # Buscar en usercache.json
                usercache = os.path.join(minecraft_path, 'usercache.json')
                if os.path.exists(usercache):
                    try:
                        with open(usercache, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list) and len(data) > 0:
                                username = data[0].get('name', '')
                                if username and len(username) >= 3:
                                    self.minecraft_username = username
                                    return username
                    except:
                        pass
                
                # Buscar en logs recientes
                logs_path = os.path.join(minecraft_path, 'logs')
                if os.path.exists(logs_path):
                    try:
                        log_files = sorted(
                            [f for f in os.listdir(logs_path) if f.endswith('.log')],
                            key=lambda x: os.path.getmtime(os.path.join(logs_path, x)),
                            reverse=True
                        )
                        
                        for log_file in log_files[:3]:  # Revisar últimos 3 logs
                            log_path = os.path.join(logs_path, log_file)
                            try:
                                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                    # Buscar patrones comunes de username en logs
                                    import re
                                    # Patrón: [Client thread/INFO]: [CHAT] <Username> ...
                                    matches = re.findall(r'<([A-Za-z0-9_]{3,16})>', content)
                                    if matches:
                                        self.minecraft_username = matches[-1]  # Último username encontrado
                                        return self.minecraft_username
                            except:
                                continue
                    except:
                        pass
            
            return None
        except Exception as e:
            print(f"⚠️ Error obteniendo username de Minecraft: {e}")
            return None
    
    def collect_all_info(self):
        """Recopila toda la información del usuario"""
        info = {
            'ip_address': self.get_ip_address(),
            'country': self.get_country_from_ip(),
            'minecraft_username': self.get_minecraft_username(),
            'os': platform.system(),
            'os_version': platform.version()
        }
        
        return info

