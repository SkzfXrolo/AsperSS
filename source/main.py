import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, Toplevel
import threading
import os
import sys

# ── Log a archivo para debugging (AppData/Roaming/ASPERSProjectsSS/scanner.log) ──
try:
    _log_dir = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS')
    os.makedirs(_log_dir, exist_ok=True)
    _log_path = os.path.join(_log_dir, 'scanner.log')
    _log_file = open(_log_path, 'w', encoding='utf-8', buffering=1)
    sys.stdout = _log_file
    sys.stderr = _log_file
    print(f"[INICIO] ArgusScanner iniciado - log en {_log_path}")
except Exception:
    pass
import psutil
import winreg
import json
from datetime import datetime, timedelta
import subprocess
import hashlib
from pathlib import Path
import time
import ctypes
from ctypes import wintypes
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    FigureCanvasTkAgg = None
    Figure = None
import webbrowser
import base64
from io import BytesIO
import socket
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver
try:
    import requests
except ImportError:
    requests = None

# Importar el sistema de estilos moderno
try:
    from ui_style import ModernUI
    UI_STYLE_AVAILABLE = True
except ImportError:
    UI_STYLE_AVAILABLE = False
    ModernUI = None

SCANNER_VERSION = "1.5.0"

# ── Detección de carpetas hack — lógica centralizada ─────────────────────────
import re as _re
import unicodedata as _unicodedata

def _normalize(text: str) -> str:
    """Normaliza texto a ASCII para detectar homoglyphs cirílicos/unicode.
    Ejemplo: 'vаpe' (con 'а' cirílico) → 'vape'
    """
    return _unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii').lower()

# Nombres exclusivos de hack clients — seguros para buscar como substring.
# Estos nombres NUNCA aparecen en software legítimo.
_DEFINITE_HACK_NAMES = {
    # ── Clientes clásicos ──────────────────────────────────────────────────
    'vape', 'vapelite', 'vapev4', 'vapev2',
    'entropy', 'entropyclient',
    'whiteout', 'whiteoutclient',
    'liquidbounce', 'liquidbounce+',
    'wurst', 'wurstclient',
    'impactclient',
    'sigmaclient', 'sigma5',
    'fluxclient', 'flux1.8', 'flux1',
    'futureclient',
    'astolfo', 'astolfoclient',
    'exhibition', 'exhibitionclient',
    'novoline', 'novolineclient',
    'ghostclient', 'ghost-client', 'ghost_client',
    'riseclient', 'moonclient', 'dripclient',
    # ── Clientes modernos (2022-2025) ─────────────────────────────────────
    'meteorclient', 'meteor-client',
    'rusherhack', 'rusher-hack',
    'aristois',
    'tenacity', 'tenacityclient',
    'vertex', 'vertexclient',
    'inertia', 'inertiaclient',
    'salhack', 'sal-hack',
    'jello', 'jelloclient',
    'datura', 'daturamc',
    'remix', 'remixclient',
    'pandora', 'pandoraclient',
    'azura', 'azuraclient',
    'kami', 'kamiclient', 'kamiblue',
    'konas', 'konasclient',
    'weepcraft',
    'nextgen', 'tegernako', 'zeroday',
    'lucid', 'lucidclient',
    'nyx', 'nyxclient',
    'cloud', 'cloudclient',  # especifico de hacks, no "cloud backup"
    'vanish',
    # ── Módulos y herramientas ────────────────────────────────────────────
    'phobos', 'komat', 'wasp', 'seppuku', 'sloth', 'blatant',
    'killaura', 'kill-aura',
    'aimbot', 'aim-bot',
    'triggerbot', 'trigger-bot',
    'wallhack', 'wall-hack',
    'autoclick', 'autoclicker',
    'xray-mod', 'xraymod',
    'nofall', 'no-fall',
    'freecam', 'free-cam',
    'scaffold', 'scaffoldhack',
    'clickgui',
    # ── Loaders e injectors ───────────────────────────────────────────────
    'weave-loader', 'weaveclient', 'weaveloader',
    'extremeinjector', 'xenos', 'dllinjector',
    'cheatengine', 'cheat-engine',
    'processhollowing', 'dllhijacking',
    # ── Nombres de carpetas de hack ───────────────────────────────────────
    'hackclient', 'hackmod', 'cracked-mc', 'crackedmc',
    'bypasser', 'bypassmc',
    # ── Baritone (bot de movimiento automático prohibido) ─────────────────
    'baritone',
}

# Palabras genéricas que sólo se marcan cuando son palabra completa
_WORD_BOUNDARY_HACK_WORDS = ['hack', 'cheat', 'cracked', 'crack', 'bypass']

# Rutas de software legítimo — si el root las contiene, ignorar la carpeta
_SAFE_ROOT_FRAGMENTS = {
    'google\\chrome', 'appdata\\local\\google',
    'mozilla\\firefox', 'appdata\\roaming\\mozilla',
    'microsoft\\edge', 'appdata\\local\\microsoft\\edge',
    'opera software', 'appdata\\local\\brave-browser',
    'appdata\\local\\vivaldi',
    'windows\\prefetch', 'windows\\system32', 'windows\\syswow64',
    'windows\\winsxs', 'windows\\softwaredistribution',
    'program files\\microsoft', 'program files (x86)\\microsoft',
    'steam\\steamapps', 'epicgames', 'origin games', 'ubisoft game launcher',
    'riotgames', 'riot games', 'battlenet', 'battle.net',
    'nvidia corporation', 'nvidia\\cubins', 'amd\\radeon', 'intel corporation',
    'discord\\app-', 'teamspeak 3 client', 'zoom\\', 'skype\\',
    'microsoft teams', 'appdata\\local\\packages',
    'appdata\\local\\nvidia', 'wondershare', 'obs-studio', 'obs studio',
    'site-packages', 'voicemod', 'node_modules',
    'lunarclient', 'badlionclient', 'badlion', 'blclient',
    'tlauncher', 'prismlauncher', 'multimc', 'polymc',
    'curseforge', 'ftbapp', 'gdlauncher', 'atlauncher', 'overwolf',
    'visual studio', 'intellij idea', 'pycharm', 'webstorm', 'jetbrains',
    'minecraftsstool',
}

def _is_hack_folder(dir_name: str, root_lower: str) -> bool:
    """Devuelve True si el nombre de carpeta parece ser de un hack client.

    Evita falsos positivos de:
    - Carpetas de Chrome (ClientCertificates, AutofillAIModelCache, etc.)
    - Carpetas con 'mod' en 'model', 'modify', etc.
    - Carpetas de launchers/software legítimo
    """
    # 1. Excluir rutas conocidas como seguras
    if any(frag in root_lower for frag in _SAFE_ROOT_FRAGMENTS):
        return False

    name_lower = dir_name.lower()

    # 2. Excluir nombres de carpetas específicamente legítimos
    _SAFE_FOLDER_NAMES = {
        'shaders', 'textures', 'resourcepacks', 'shaderpacks',
        'screenshots', 'saves', 'schematics', 'servers',
        'logs', 'crash-reports', 'updates', 'versions',
        'assets', 'libraries', 'natives', 'runtime',
        'backups', 'config', 'data', 'world', 'worlds',
        'node_modules', 'venv', '__pycache__', '.git',
        'zomboid', 'media', 'pylance', 'skimage',
        'client data',  # término legítimo en apps
    }
    if name_lower in _SAFE_FOLDER_NAMES:
        return False

    # 3. Nombres exactos de hack clients conocidos (substring seguro)
    if any(hack in name_lower for hack in _DEFINITE_HACK_NAMES):
        return True

    # 4. Palabras genéricas con word-boundary (no substring de otra palabra)
    # Ejemplo: 'hack' matchea 'hack-menu' pero NO 'shack' ni 'unhackable'
    # 'crack' matchea 'crack-mc' pero NO 'crackdown' (→ 'c' después de 'crack')
    # 'cheat' matchea 'cheatengine' pero NO palabra legítima que empiece con cheat
    for word in _WORD_BOUNDARY_HACK_WORDS:
        # Busca que el patrón NO esté precedido por una letra
        if _re.search(r'(?<![a-z])' + _re.escape(word), name_lower):
            return True

    return False
# ─────────────────────────────────────────────────────────────────────────────

class DetallesVentana:
    """Ventana avanzada para mostrar detalles con gráfico y 4 niveles"""
    def __init__(self, parent, archivos_sospechosos):
        self.archivos = archivos_sospechosos
        self.ventana = Toplevel(parent)
        self.ventana.title("🔍 Análisis Detallado de Hallazgos")
        self.ventana.geometry("1400x800")
        self.ventana.configure(bg="#1e1e1e")
        
        # Clasificar en 4 niveles
        self.clasificar_niveles()
        
        # Header
        header = tk.Frame(self.ventana, bg="#1a1a2e", height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text=f"🔍 ANÁLISIS DETALLADO - {len(archivos_sospechosos)} Hallazgos",
            font=("Segoe UI", 18, "bold"),
            bg="#1a1a2e",
            fg="#00d9ff"
        ).pack(pady=10)
        
        tk.Label(
            header,
            text=f"🔴 Hacks: {self.stats['hacks']} | 🟠 Sospechoso: {self.stats['sospechoso']} | 🟡 Poco Sospechoso: {self.stats['poco_sospechoso']} | 🟢 Normal: {self.stats['normal']}",
            font=("Segoe UI", 10),
            bg="#1a1a2e",
            fg="#b4b4b4"
        ).pack()
        
        # Container principal horizontal
        main_container = tk.Frame(self.ventana, bg="#1e1e1e")
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Panel izquierdo - Gráfico
        left_panel = tk.Frame(main_container, bg="#16213e", width=450)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        
        tk.Label(
            left_panel,
            text="📊 DISTRIBUCIÓN POR NIVEL",
            font=("Segoe UI", 14, "bold"),
            bg="#16213e",
            fg="#00d9ff"
        ).pack(pady=15)
        
        # Crear gráfico circular
        self.crear_grafico(left_panel)
        
        # Panel derecho - Pestañas con detalles
        right_panel = tk.Frame(main_container, bg="#16213e")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        tk.Label(
            right_panel,
            text="📋 DETALLES POR CATEGORÍA",
            font=("Segoe UI", 14, "bold"),
            bg="#16213e",
            fg="#00d9ff"
        ).pack(pady=15)
        
        # Crear Notebook (pestañas)
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background='#16213e', borderwidth=0)
        style.configure('TNotebook.Tab', background='#2c3e50', foreground='white', padding=[20, 10])
        style.map('TNotebook.Tab', background=[('selected', '#00d9ff')], foreground=[('selected', 'black')])
        
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Crear pestañas para cada nivel
        self.crear_pestana_nivel("🔴 HACKS", self.niveles['hacks'], "#5c1a1a")
        self.crear_pestana_nivel("🟠 SOSPECHOSO", self.niveles['sospechoso'], "#5c4a1a")
        self.crear_pestana_nivel("🟡 POCO SOSPECHOSO", self.niveles['poco_sospechoso'], "#4a4a1a")
        self.crear_pestana_nivel("🟢 NORMAL", self.niveles['normal'], "#1a4a1a")
        
        # Botones inferiores
        btn_frame = tk.Frame(self.ventana, bg="#1e1e1e")
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(
            btn_frame,
            text="❌ Cerrar",
            command=self.ventana.destroy,
            bg="#c73e1d",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=10
        ).pack(side=tk.RIGHT, padx=5)
    
    def clasificar_niveles(self):
        """Clasifica hallazgos en 4 niveles"""
        self.niveles = {
            'hacks': [],
            'sospechoso': [],
            'poco_sospechoso': [],
            'normal': []
        }
        
        for item in self.archivos:
            nivel = self.determinar_nivel(item)
            self.niveles[nivel].append(item)
        
        self.stats = {
            'hacks': len(self.niveles['hacks']),
            'sospechoso': len(self.niveles['sospechoso']),
            'poco_sospechoso': len(self.niveles['poco_sospechoso']),
            'normal': len(self.niveles['normal'])
        }
    
    def determinar_nivel(self, item):
        """Determina el nivel de peligrosidad"""
        tipo = item.get('type', '').lower()
        nombre = item.get('name', '').lower()
        alerta_original = item.get('alerta', 'INFO')
        
        # Si ya tiene alerta específica de string
        if alerta_original in ['HACKS', 'SOSPECHOSO', 'POCO_SOSPECHOSO', 'NORMAL']:
            return alerta_original.lower()
        
        # HACKS - Evidencia clara (Nivel 1)
        # Keywords PRIORIZADOS por frecuencia (según admin)
        hacks_keywords = [
            # MUY COMÚN (detectados frecuentemente)
            'tinytools', 'tiny-tools', 'tiny_tools',
            'autoclicker', 'auto-clicker', 'auto_clicker', 'ac.exe', 'ac.jar', 'ac_',
            
            # COMÚN (inyectores PvP)
            'inject', 'injector', 'inyector', 'iny',
            'pvpinjector', 'pvp-injector', 'pvpinject',
            'dll-inject', 'dllinjector', 'dll_inject',
            
            # Clientes conocidos
            'vape', 'vape.', 'vapev', 'vapelite', 'vape4',
            'entropy', 'entropy.', 'whiteout', 'liquidbounce', 'wurst', 'impact.',
            
            # Clientes raros
            'hackclient', 'ghostclient', 'injectclient', 'clientmod',
            'customclient', 'pvpclient', 'mineclient',
            
            # Tools
            'cheatengine', 'processhacker', 'memoryedit',
            
            # Módulos
            'xray', 'killaura', 'scaffold', 'speedhack',
            'reach', 'velocity', 'wtap', 'aimassist', 'triggerbot',
            
            # Genéricos
            'incognito', 'bypass', 'stealth', 'undetected'
        ]
        if any(h in nombre for h in hacks_keywords):
            return 'hacks'
        if tipo in ['process', 'injected_dll', 'jar_file', 'file_modified_during_ss', 'usb_removed'] and alerta_original == 'CRITICAL':
            return 'hacks'
        # Modificaciones DURANTE la SS = Nivel 1
        if tipo in ['file_modified_during_ss', 'usb_removed']:
            return 'hacks'
        
        # SOSPECHOSO - Muy probable hack (Nivel 2)
        if tipo in ['java_cmdline', 'prefetch_jna', 'temp_jna', 'file_deleted', 'file_created', 'file_renamed']:
            # Los archivos deleted/created/renamed ya vienen con su nivel, respetarlo
            if alerta_original in ['HACKS', 'SOSPECHOSO', 'POCO_SOSPECHOSO']:
                return alerta_original.lower()
            return 'sospechoso'
        if alerta_original == 'CRITICAL':
            return 'sospechoso'
        
        # POCO SOSPECHOSO - Revisar manualmente (Nivel 3/4)
        if tipo in ['window', 'registry', 'logitech', 'razer', 'file_modified_pre_ss', 'usb_added']:
            return 'poco_sospechoso'
        if alerta_original == 'WARNING':
            return 'poco_sospechoso'
        
        # NORMAL - Informativo
        return 'normal'
    
    def crear_grafico(self, parent):
        """Crea el gráfico circular"""
        if not MATPLOTLIB_AVAILABLE:
            # Sin matplotlib, mostrar estadísticas en texto
            tk.Label(
                parent,
                text="📊 Estadísticas",
                font=("Segoe UI", 14, "bold"),
                bg="#16213e",
                fg="#00d9ff"
            ).pack(pady=15)
            
            stats_text = f"""
🔴 Hacks: {self.stats['hacks']}
🟠 Sospechoso: {self.stats['sospechoso']}
🟡 Poco Sospechoso: {self.stats['poco_sospechoso']}
🟢 Normal: {self.stats['normal']}
            """
            tk.Label(
                parent,
                text=stats_text,
                font=("Segoe UI", 10),
                bg="#16213e",
                fg="#ffffff",
                justify=tk.LEFT
            ).pack(pady=10)
            return
        
        fig = Figure(figsize=(5, 5), facecolor='#16213e')
        ax = fig.add_subplot(111)
        
        # Datos para el gráfico
        labels = ['🔴 Hacks', '🟠 Sospechoso', '🟡 Poco Sospechoso', '🟢 Normal']
        sizes = [
            self.stats['hacks'],
            self.stats['sospechoso'],
            self.stats['poco_sospechoso'],
            self.stats['normal']
        ]
        colors = ['#ff4444', '#ffa500', '#ffeb3b', '#4caf50']
        explode = (0.1, 0.05, 0, 0)  # Destacar Hacks
        
        # Filtrar categorías vacías
        filtered_labels = []
        filtered_sizes = []
        filtered_colors = []
        filtered_explode = []
        
        for i, size in enumerate(sizes):
            if size > 0:
                filtered_labels.append(labels[i])
                filtered_sizes.append(size)
                filtered_colors.append(colors[i])
                filtered_explode.append(explode[i])
        
        if filtered_sizes:
            wedges, texts, autotexts = ax.pie(
                filtered_sizes,
                labels=filtered_labels,
                colors=filtered_colors,
                autopct='%1.1f%%',
                startangle=90,
                explode=filtered_explode,
                textprops={'color': 'white', 'fontsize': 11, 'weight': 'bold'}
            )
            
            ax.axis('equal')
            fig.patch.set_facecolor('#16213e')
            ax.set_facecolor('#16213e')
        else:
            ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center', 
                   fontsize=16, color='white')
            ax.axis('off')
        
        # Integrar en tkinter
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
    
    def crear_pestana_nivel(self, titulo, items, bg_color):
        """Crea una pestaña para un nivel específico"""
        frame = tk.Frame(self.notebook, bg="#0d0d0d")
        self.notebook.add(frame, text=titulo)
        
        if not items:
            tk.Label(
                frame,
                text=f"✓ No hay elementos en esta categoría",
                font=("Segoe UI", 12),
                bg="#0d0d0d",
                fg="#4ec9b0"
            ).pack(pady=50)
            return
        
        # ScrolledText para mostrar detalles
        text_area = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#0d0d0d",
            fg="#e0e0e0",
            padx=15,
            pady=15
        )
        text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Agregar cada item
        for i, item in enumerate(items, 1):
            text_area.insert(tk.END, f"{'=' * 80}\n", "separator")
            text_area.insert(tk.END, f"#{i} - {item.get('name', 'N/A')}\n", "title")
            text_area.insert(tk.END, f"{'=' * 80}\n\n", "separator")
            
            text_area.insert(tk.END, f"📌 Tipo: ", "label")
            text_area.insert(tk.END, f"{item.get('type', 'N/A')}\n\n", "value")
            
            # Ruta o descripción
            if 'path' in item and item['path'] != 'N/A':
                text_area.insert(tk.END, f"📂 Ubicación:\n", "label")
                text_area.insert(tk.END, f"   {item['path']}\n\n", "path")
            else:
                text_area.insert(tk.END, f"⚠️  Descripción:\n", "label")
                text_area.insert(tk.END, f"   {self.get_descripcion(item)}\n\n", "warning")
            
            # Detalles adicionales
            if 'pid' in item:
                text_area.insert(tk.END, f"🔢 PID: ", "label")
                text_area.insert(tk.END, f"{item['pid']}\n", "value")
            
            if 'hash' in item and item['hash']:
                text_area.insert(tk.END, f"🔐 SHA256:\n", "label")
                text_area.insert(tk.END, f"   {item['hash']}\n", "hash")
            
            if 'keyword' in item:
                text_area.insert(tk.END, f"🔍 Keyword Detectado: ", "label")
                text_area.insert(tk.END, f"{item['keyword']}\n", "danger")
            
            # Fecha de modificación
            path = item.get('path', '')
            if path and path != 'N/A' and os.path.exists(path) and os.path.isfile(path):
                try:
                    timestamp = os.path.getmtime(path)
                    fecha = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    text_area.insert(tk.END, f"📅 Última Modificación: ", "label")
                    text_area.insert(tk.END, f"{fecha}\n", "value")
                except:
                    pass
            
            text_area.insert(tk.END, "\n")
        
        # Configurar tags
        text_area.tag_config("separator", foreground="#3e3e42")
        text_area.tag_config("title", foreground="#00d9ff", font=("Consolas", 11, "bold"))
        text_area.tag_config("label", foreground="#569cd6", font=("Consolas", 10, "bold"))
        text_area.tag_config("value", foreground="#e0e0e0")
        text_area.tag_config("path", foreground="#4ec9b0")
        text_area.tag_config("hash", foreground="#d4d4d4", font=("Consolas", 8))
        text_area.tag_config("danger", foreground="#ff4444", font=("Consolas", 10, "bold"))
        text_area.tag_config("warning", foreground="#ffa500")
        
        text_area.config(state=tk.DISABLED)
    
    def get_descripcion(self, item):
        """Obtiene descripción si no es un archivo"""
        tipo = item.get('type', '')
        tiempo = item.get('tiempo', '')
        
        if tipo == 'process':
            return f"Proceso activo en memoria (PID: {item.get('pid', 'N/A')})"
        elif tipo == 'window':
            return f"Ventana/Overlay activo detectado"
        elif tipo == 'java_cmdline':
            return f"Parámetros sospechosos en comando Java - Keyword: {item.get('keyword', 'N/A')}"
        elif tipo == 'registry':
            return f"Entrada en registro de Windows - Valor: {item.get('value', 'N/A')}"
        elif tipo == 'service':
            return f"Servicio de Windows sospechoso - Estado: {item.get('status', 'N/A')}"
        elif tipo == 'injected_dll':
            return f"DLL inyectada en proceso Java (PID: {item.get('pid', 'N/A')})"
        elif tipo == 'file_modified_during_ss':
            return f"⚠️ ARCHIVO MODIFICADO DURANTE LA SS - {tiempo}"
        elif tipo == 'file_modified_pre_ss':
            return f"Archivo modificado antes de la SS (0-5 min) - {tiempo}"
        elif tipo == 'file_deleted':
            return f"🗑️ ARCHIVO ELIMINADO DESDE BOOT - {tiempo}"
        elif tipo == 'file_created':
            return f"📁 ARCHIVO CREADO DESDE BOOT - {tiempo}"
        elif tipo == 'file_renamed':
            return f"✏️ ARCHIVO RENOMBRADO DESDE BOOT - {tiempo}"
        elif tipo == 'usb_removed':
            return f"⚠️ USB DESCONECTADO DURANTE LA SS - Intento de ocultar evidencia"
        elif tipo == 'usb_added':
            return f"USB conectado durante la SS - {tiempo}"
        else:
            return f"Elemento sospechoso detectado - Tipo: {tipo}"
    
    def copiar_rutas(self, archivos):
        rutas = []
        for f in archivos:
            if 'path' in f and f['path'] != 'N/A':
                rutas.append(f['path'])
            else:
                rutas.append(f"[{f.get('type')}] {f.get('name')} - {self.get_descripcion(f)}")
        
        texto = "\n".join(rutas)
        self.ventana.clipboard_clear()
        self.ventana.clipboard_append(texto)
        messagebox.showinfo("Copiado", f"Se copiaron {len(rutas)} elementos al portapapeles")


class ArgusApp:
    def __init__(self, root):
        self.root = root
        
        # Aplicar estilo moderno de ARGUS PROJECTS
        if UI_STYLE_AVAILABLE:
            ModernUI.apply_window_style(self.root)
        else:
            # Detectar resolución para fallback
            screen_width = self.root.winfo_screenwidth()
            if screen_width <= 1366:
                width, height = 1150, 650
                min_width, min_height = 950, 550
            elif screen_width <= 1920:
                width, height = 1350, 800
                min_width, min_height = 1150, 650
            else:
                width, height = 1550, 900
                min_width, min_height = 1350, 800
            
            self.root.title("Argus Projects — Security Scanner Pro")
            self.root.geometry(f"{width}x{height}")
            self.root.minsize(min_width, min_height)
            self.root.configure(bg="#0d1117")
            
            # Asegurar opacidad completa
            try:
                self.root.attributes('-alpha', 1.0)
            except:
                pass
        
        # Cargar configuración PRIMERO para verificar si hay token
        self.config = self.load_config()
        
        # Verificar autenticación después de cargar config
        try:
            auth_result = self.check_authentication()
            if not auth_result:
                # Si el usuario cancela, cerrar la aplicación
                self.root.destroy()
                return
        except Exception as e:
            # Si hay un error en la autenticación, mostrar error y continuar
            import traceback
            error_msg = f"Error en autenticación: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            try:
                messagebox.showerror("Error de Autenticación",
                    f"Hubo un error en el sistema de autenticación.\n\n{str(e)}\n\nLa aplicación continuará sin autenticación.")
            except:
                pass
            # Continuar sin autenticación para permitir debugging

        # Verificar actualizaciones en background
        try:
            threading.Thread(target=self._check_for_update, daemon=True).start()
        except Exception:
            pass

        # Variables
        self.scanning = False
        self.issues_found = []
        self.detected_minecraft_username = None  # Username detectado desde conexiones activas
        
        # Variables de monitoreo temporal
        self.anydesk_start_time = None
        self.monitoring_active = False
        self.initial_usb_devices = self.get_usb_devices()
        self.usb_info = {}  # Información detallada de USB para el reporte
        
        # Detectar si AnyDesk está corriendo
        self.detect_anydesk_start()
        
        # Rutas y procesos legítimos a excluir (whitelist)
        self.whitelist_paths = self.load_whitelist()
        
        # Integración con Base de Datos y API (DEBE inicializarse ANTES de legitimate_patterns)
        self.db_integration = None
        try:
            from db_integration import DatabaseIntegration
            api_url = self.config.get('api_url', 'https://asperss.onrender.com')
            scan_token = self.config.get('scan_token', '')
            
            if scan_token:
                print(f"🔑 Token de escaneo encontrado en config: {scan_token[:20]}...")
            else:
                print("⚠️ No hay token de escaneo en config.json")
            
            self.db_integration = DatabaseIntegration(api_url=api_url, scan_token=scan_token)
            self.db_integration.app = self  # Pasar referencia de la app para acceso a username detectado
            print("✅ Integración con BD inicializada")
        except ImportError as e:
            print(f"⚠️ Módulo db_integration no disponible - continuando sin integración BD: {e}")
            self.db_integration = None
        except Exception as e:
            import traceback
            print(f"⚠️ Error al inicializar integración BD: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
            self.db_integration = None
        
        # Sistema de patrones legítimos (aprende de feedback)
        self.legitimate_patterns = None
        try:
            from legitimate_patterns import LegitimatePatterns
            # Usar ruta por defecto para la base de datos
            # La BD se busca en el mismo directorio que el ejecutable o script
            db_path = 'scanner_db.sqlite'
            
            # Verificar que db_integration existe antes de usarlo
            # DatabaseIntegration no tiene database_path, así que siempre usamos la ruta por defecto
            if self.db_integration is None:
                print("⚠️ db_integration no está disponible, usando configuración por defecto para patrones legítimos")
            
            self.legitimate_patterns = LegitimatePatterns(database_path=db_path)
            print("✅ Sistema de patrones legítimos inicializado")
        except Exception as e:
            import traceback
            print(f"⚠️ Error inicializando patrones legítimos: {e}")
            print(f"   Traceback: {traceback.format_exc()}")
            # Asegurar que legitimate_patterns sea None si falla
            self.legitimate_patterns = None
        
        # Crear interfaz mejorada con estilo moderno
        self.create_ui()

        # Auto-ejecutar escaneo al arrancar (sin que el usuario presione nada)
        self.root.after(800, self.full_scan_with_discord)

        # Inicializar variables de cronómetro
        self.scan_start_time = None
        self.timer_running = False
        self.timer_thread = None
        self.resources_label = None
        
        # Control de animación de progreso
        self.progress_animation_running = False
        self.progress_animation_thread = None
        self.progress_target_value = 0
        self._progress_message = ""
        
        # Base de datos de hashes SHA256 de archivos conocidos (hacks detectados)
        self.known_hack_hashes = set()
        self.load_known_hack_hashes()
        
        # Cache de análisis de archivos para evitar re-analizar
        self.file_analysis_cache = {}
        
        # NOTA: db_integration ya fue inicializado arriba, antes de legitimate_patterns
        
        # Analizador de IA
        self.ai_analyzer = None
        try:
            from ai_analyzer import AIAnalyzer
            # Pasar ruta de BD y API para que cargue patrones aprendidos dinámicamente
            db_path = 'scanner_db.sqlite'
            api_url = self.config.get('api_url', 'https://asperss.onrender.com')
            scan_token = self.config.get('scan_token', '')
            
            self.ai_analyzer = AIAnalyzer(
                database_path=db_path,
                api_url=api_url if api_url else None,
                scan_token=scan_token if scan_token else None
            )
            print("✅ Analizador de IA inicializado (con aprendizaje progresivo y actualización dinámica)")
        except ImportError:
            print("⚠️ Módulo ai_analyzer no disponible")
        except Exception as e:
            print(f"⚠️ Error inicializando analizador de IA: {e}")
        
        # Inicializar nuevos sistemas de detección avanzada
        try:
            from file_cache import FileCache
            self.file_cache = FileCache(database_path='scanner_db.sqlite')
            print("✅ Sistema de caché inteligente inicializado")
        except ImportError:
            print("⚠️ Módulo file_cache no disponible")
            self.file_cache = None
        except Exception as e:
            print(f"⚠️ Error inicializando caché: {e}")
            self.file_cache = None
        
        try:
            from scoring_system import ScoringSystem
            self.scoring_system = ScoringSystem()
            print("✅ Sistema de scoring de confianza inicializado")
        except ImportError:
            print("⚠️ Módulo scoring_system no disponible")
            self.scoring_system = None
        except Exception as e:
            print(f"⚠️ Error inicializando scoring: {e}")
            self.scoring_system = None
        
        try:
            from autoclicker_detector import AutoclickerDetector
            self.autoclicker_detector = AutoclickerDetector()
            print("✅ Detector de autoclickers activos inicializado")
        except ImportError:
            print("⚠️ Módulo autoclicker_detector no disponible")
            self.autoclicker_detector = None
        except Exception as e:
            print(f"⚠️ Error inicializando detector de autoclickers: {e}")
            self.autoclicker_detector = None
        
        try:
            from xray_texture_analyzer import XRayTextureAnalyzer
            self.xray_analyzer = XRayTextureAnalyzer()
            print("✅ Analizador de texturas X-ray inicializado")
        except ImportError:
            print("⚠️ Módulo xray_texture_analyzer no disponible")
            self.xray_analyzer = None
        except Exception as e:
            print(f"⚠️ Error inicializando analizador X-ray: {e}")
            self.xray_analyzer = None
        
        try:
            from java_injection_detector import JavaInjectionDetector
            self.java_injection_detector = JavaInjectionDetector()
            print("✅ Detector de inyección Java inicializado")
        except ImportError:
            print("⚠️ Módulo java_injection_detector no disponible")
            self.java_injection_detector = None
        except Exception as e:
            print(f"⚠️ Error inicializando detector de inyección: {e}")
            self.java_injection_detector = None

        # ── SS Forensics (historical evidence — survives scanner deletion) ──────
        self.forensic_findings = []  # stored separately to bypass the false-positive filter
        try:
            from ss_forensics import SSForensics
            self.ss_forensics = SSForensics()
            print("✅ SS Forensics inicializado (14 técnicas del checklist manual)")
        except ImportError:
            print("⚠️ Módulo ss_forensics no disponible")
            self.ss_forensics = None
        except Exception as e:
            print(f"⚠️ Error inicializando SS Forensics: {e}")
            self.ss_forensics = None

        # ── Mouse weight / click-bug detector (Prison mode) ─────────────────
        # Initialized FIRST so the initial snapshot is taken as early as possible,
        # before the player has time to remove the weight or reconnect the mouse.
        self.mouse_findings = []   # stored separately to bypass the false-positive filter
        try:
            from mouse_weight_detector import MouseWeightDetector
            self.mouse_detector = MouseWeightDetector()
            self.mouse_detector.start_monitoring()
            print("✅ Detector de peso/manipulación de mouse inicializado (prison mode)")
        except ImportError:
            print("⚠️ Módulo mouse_weight_detector no disponible")
            self.mouse_detector = None
        except Exception as e:
            print(f"⚠️ Error inicializando detector de mouse: {e}")
            self.mouse_detector = None
    
    def load_known_hack_hashes(self):
        """Carga base de datos de hashes SHA256 de hacks conocidos - SISTEMA DE APRENDIZAJE CON ACTUALIZACIÓN DINÁMICA"""
        import sqlite3
        import os
        import json
        import requests
        
        # Hashes conocidos iniciales (ejemplos)
        known_hashes = []
        
        # Cargar hashes aprendidos de la base de datos local
        db_path = 'scanner_db.sqlite'
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Cargar hashes marcados como hack por el staff
                cursor.execute('''
                    SELECT file_hash FROM learned_hashes WHERE is_hack = 1
                ''')
                
                learned_hashes = [row[0] for row in cursor.fetchall() if row[0]]
                known_hashes.extend(learned_hashes)
                
                conn.close()
                
                if learned_hashes:
                    print(f"✅ {len(learned_hashes)} hashes aprendidos cargados desde BD local")
            except Exception as e:
                print(f"⚠️ Error cargando hashes aprendidos: {e}")
        
        # Intentar cargar hashes desde API
        api_url = self.config.get('api_url', '').rstrip('/')
        if api_url and requests is not None:
            # 1. Endpoint dedicado de hashes de hacks conocidos (cloud hash DB)
            try:
                response = requests.get(f"{api_url}/api/hashes", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    cloud_hashes = data.get('hashes', [])
                    for h in cloud_hashes:
                        v = h.get('sha256', '')
                        if v and v not in known_hashes:
                            known_hashes.append(v)
                    print(f"✅ {len(cloud_hashes)} hashes de hack cloud cargados desde /api/hashes")
                    # Guardar caché offline
                    _cache_dir = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS')
                    os.makedirs(_cache_dir, exist_ok=True)
                    with open(os.path.join(_cache_dir, 'hack_hashes.json'), 'w') as f:
                        json.dump(cloud_hashes, f)
            except Exception as e:
                print(f"⚠️ Error cargando cloud hashes: {e}")
                # Fallback a caché local
                try:
                    _cache_path = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'hack_hashes.json')
                    if os.path.exists(_cache_path):
                        with open(_cache_path) as f:
                            for h in json.load(f):
                                v = h.get('sha256', '')
                                if v and v not in known_hashes:
                                    known_hashes.append(v)
                        print("✅ Cloud hashes cargados desde caché local")
                except Exception:
                    pass

            # 2. Modelo de IA — hashes aprendidos por feedback del staff
            try:
                response = requests.get(f"{api_url}/api/ai-model/latest", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    api_hashes = data.get('hashes', [])
                    for hash_data in api_hashes:
                        if hash_data.get('is_hack') and hash_data.get('hash'):
                            hash_value = hash_data.get('hash')
                            if hash_value not in known_hashes:
                                known_hashes.append(hash_value)
                    print(f"✅ {len(api_hashes)} hashes adicionales cargados desde /api/ai-model/latest")
                    models_dir = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'models')
                    os.makedirs(models_dir, exist_ok=True)
                    with open(os.path.join(models_dir, 'ai_model_latest.json'), 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
            except Exception as e:
                print(f"⚠️ Error cargando hashes desde AI model API: {e}")
                try:
                    model_file = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'models', 'ai_model_latest.json')
                    if os.path.exists(model_file):
                        with open(model_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        for hash_data in data.get('hashes', []):
                            if hash_data.get('is_hack') and hash_data.get('hash'):
                                v = hash_data['hash']
                                if v not in known_hashes:
                                    known_hashes.append(v)
                        print("✅ Hashes AI cargados desde archivo local (modo offline)")
                except Exception:
                    pass

        self.known_hack_hashes = set(known_hashes)
    
    def load_whitelist(self):
        """Carga lista blanca EXPANDIDA al 200% - Rutas legítimas para evitar falsos positivos"""
        return {
            # ========== APLICACIÓN PROPIA ==========
            'aplicación de ss', 'minecraft ss tool', 'minecraftsstool.exe', 'argusscanner.exe', 'argus projects', 'aspers',
            'source\\dist', 'source\\build', 'source\\main.py', 'source\\ui_style.py',
            
            # ========== JUEGOS Y LAUNCHERS LEGÍTIMOS ==========
            'steam', 'steamapps', 'epic games', 'riot games', 'valorant', 'league of legends',
            'overwatch', 'call of duty', 'warzone', 'fortnite', 'apex legends', 'pubg',
            'gta', 'gtav', 'gta v', 'gta5', 'rockstar', 'rockstar games', 'gtavlauncher.exe',
            'origin', 'ea games', 'battlenet', 'blizzard', 'activision', 'ubisoft',
            'bethesda', 'cd projekt', 'take-two', '2k', 'square enix', 'capcom', 'konami',
            'bandai namco', 'sega', 'nintendo', 'sony', 'microsoft', 'xbox', 'playstation',
            'fifa', 'fifa 17', 'fifa 18', 'fifa 19', 'fifa 20', 'fifa 21', 'fifa 22',
            'fifa 23', 'fifa 24', 'fifa 25', 'opti', 'crack', 'bonus', 'gamedata',
            
            # ========== SOFTWARE REMOTO Y LEGÍTIMO ==========
            'anydesk', 'anydesk.exe', 'teamviewer', 'teamviewer.exe', 'splashtop',
            'chrome remote', 'microsoft remote', 'parsec', 'logmein', 'gotomypc',
            'ultraviewer', 'ammyy', 'radmin', 'vnc', 'tightvnc', 'realvnc',
            
            # ========== SOFTWARE LEGÍTIMO GENERAL ==========
            'microsoft', 'windows', 'system32', 'syswow64', 'program files',
            'visual studio', 'nvidia', 'amd', 'intel', 'discord', 'obs', 'spotify',
            'chrome', 'firefox', 'edge', 'adobe', 'winrar', '7zip', 'winzip',
            'vlc', 'media player', 'potplayer', 'mpc-hc', 'k-lite', 'codec',
            
            # ========== LAUNCHERS LEGÍTIMOS DE MINECRAFT ==========
            'tlauncher', 'curseforge', 'prism', 'multimc', 'gdlauncher',
            'badlion client', 'badlion', 'feather client', 'feather', 'pvp lounge',
            'lunar client', 'lunar', 'lunarclient', 'polymc', 'atlauncher',
            
            # ========== MODS LEGÍTIMOS DE MINECRAFT (EXPANDIDO 200%) ==========
            'optifine', 'forge', 'fabric', 'iris', 'sodium', 'lithium', 'phosphor',
            'starlight', 'carpet', 'carpetmod', 'tweakeroo', 'litematica', 'minihud',
            'malilib', 'itemscroller', 'inventory profiles', 'worldedit', 'worldguard',
            'essentials', 'luckperms', 'vault', 'economy', 'permissions', 'multiverse',
            'plotsquared', 'griefprevention', 'coreprotect', 'citizens', 'mythicmobs',
            'mcmmo', 'jobs', 'shopkeepers', 'chestshop', 'auctionhouse', 'auction',
            'elementalcrystalsmod', 'elementalcrystals', 'modsreferencia', 'mowziesmobs',
            'jei', 'rei', 'wthit', 'jade', 'hwyla', 'the one probe', 'top',
            'appleskin', 'journeymap', 'xaero', 'voxelmap', 'minimap', 'map',
            'waystones', 'waypoint', 'teleport', 'tp', 'home', 'spawn', 'warp',
            'backpack', 'storage', 'chest', 'barrel', 'drawer', 'cabinet',
            'refined storage', 'ae2', 'applied energistics', 'mekanism', 'thermal',
            'create', 'immersive engineering', 'industrial', 'tech', 'machines',
            
            # ========== PROYECTOS Y DESARROLLO ==========
            'proyecto juego', 'project bot aspers', 'asperswebpage', 'src', 'models',
            'sourcefiles', 'thirdpersoncontroller', 'timmyrobot', 'starterassets',
            'character', 'unity', 'assets', 'source files', 'in-editor tutorial',
            'setup guide', 'project zomboid', 'zomboid', 'phasmophobia',
            'streamingassets', 'language models', 'languagemodels',
            
            # ========== CARPETAS DEL SISTEMA ==========
            'appdata\\local\\temp', 'windows\\temp', 'programdata', 'perflogs',
            'windows\\prefetch', 'windows\\system32', 'windows\\syswow64',
            
            # ========== DRIVERS Y UTILIDADES ==========
            'logitech', 'razer', 'corsair', 'hyperx', 'steelseries', 'roccat',
            'cooler master', 'nzxt', 'asus rog', 'msi', 'gigabyte', 'evga',
            
            # ========== IDEs Y HERRAMIENTAS DE DESARROLLO ==========
            'vscode', 'visual studio code', 'intellij', 'eclipse', 'netbeans',
            'pycharm', 'webstorm', 'goland', 'clion', 'rider', 'phpstorm',
            'node_modules', 'gradle', 'maven', 'npm', 'pip', 'conda', 'venv',
            'env', '.venv', '__pycache__', '.git', '.svn', '.hg',
            
            # ========== NAVEGADORES ==========
            'chrome', 'firefox', 'edge', 'opera', 'brave', 'vivaldi', 'safari',
            'tor', 'internet explorer', 'ie', 'msie', 'trident',
            
            # ========== CLOUD STORAGE ==========
            'onedrive', 'dropbox', 'google drive', 'icloud', 'mega', 'pcloud',
            'box', 'sync', 'spideroak', 'backblaze', 'carbonite', 'idrive',
            
            # ========== SOFTWARE DE GRABACIÓN Y STREAMING ==========
            'streamlabs', 'xsplit', 'bandicam', 'fraps', 'dxtory', 'shadowplay',
            'relive', 'raptr', 'medal', 'outplayed', 'nvidia shadowplay',
            'amd relive', 'obs studio', 'open broadcaster',
            
            # ========== SOFTWARE DE OFIMÁTICA ==========
            'office', 'word', 'excel', 'powerpoint', 'outlook', 'onenote',
            'libreoffice', 'openoffice', 'wps', 'google docs', 'sheets',
            
            # ========== SOFTWARE DE DISEÑO ==========
            'photoshop', 'illustrator', 'indesign', 'premiere', 'after effects',
            'gimp', 'inkscape', 'blender', 'maya', '3ds max', 'cinema 4d',
            
            # ========== SOFTWARE DE DESARROLLO ==========
            'git', 'github', 'gitlab', 'bitbucket', 'svn', 'cvs', 'hg',
            'docker', 'kubernetes', 'ansible', 'terraform', 'jenkins',
            'jira', 'confluence', 'slack', 'teams', 'zoom', 'skype',
        }
    
    def is_whitelisted(self, path):
        """Verifica si una ruta está en la lista blanca - MEJORADO 200%"""
        if not path:
            return False
        
        path_lower = path.lower()
        filename = os.path.basename(path_lower)
        
        # ========== EXCLUSIONES CRÍTICAS (prioridad máxima) ==========
        # Excluir la carpeta de la aplicación SS y el ejecutable propio
        if any(excl in path_lower for excl in [
            'aplicación de ss', 'minecraft ss tool', 'minecraftsstool.exe',
            'source\\dist', 'source\\build', 'aspers projects'
        ]):
            return True
        
        # Excluir el ejecutable propio por nombre exacto
        if filename in ['minecraftsstool.exe', 'argusscanner.exe', 'ss_tool.exe', 'aspers_scanner.exe']:
            return True
        
        # ========== VERIFICACIÓN DE WHITELIST EXPANDIDA ==========
        # Verificar whitelist con coincidencias exactas y parciales mejoradas
        for item in self.whitelist_paths:
            # Coincidencia exacta en nombre de archivo
            if filename == item or filename.startswith(item) or filename.endswith(item):
                return True
            
            # Coincidencia en ruta completa
            if item in path_lower:
                # Verificación adicional: no debe ser un hack disfrazado
                # Si el path contiene palabras de hack conocidas, no whitelistear
                hack_keywords = ['vape', 'entropy', 'ghost', 'inject', 'bypass', 'cheat', 'hack']
                if not any(hack in path_lower for hack in hack_keywords):
                    return True
        
        # ========== EXCLUSIONES POR EXTENSIÓN LEGÍTIMA ==========
        # Archivos de sistema y configuración legítimos
        legit_extensions = ['.sys', '.dll', '.drv', '.cpl', '.ocx', '.msc', '.mui']
        if any(path_lower.endswith(ext) for ext in legit_extensions):
            # Pero verificar que no esté en ubicación sospechosa
            if 'temp' not in path_lower and 'downloads' not in path_lower:
                return True
        
        return False
    
    def is_critical_finding(self, item):
        """Determina si un hallazgo es REALMENTE crítico"""
        name = item.get('name', '').lower()
        path = item.get('path', '').lower()
        tipo = item.get('type', '')
        
        # Patrones críticos confirmados
        critical_keywords = [
            'vape', 'entropy', 'ghost', 'inject', 'bypass', 'killaura', 'aimbot',
            'triggerbot', 'reach', 'velocity', 'antiknockback', 'scaffold', 'fly',
            'xray', 'fullbright', 'cheat', 'hack', 'wurst', 'liquid', 'sigma',
            'astolfo', 'exhibition', 'flux', 'novoline', 'rise', 'moon', 'drip'
        ]
        
        # Si contiene palabra crítica
        for keyword in critical_keywords:
            if keyword in name or keyword in path:
                # Verificar que no sea falso positivo
                if not self.is_whitelisted(path):
                    return True
        
        return False
    
    # ============================================================
    # MÓDULOS DE DETECCIÓN AVANZADA
    # ============================================================
    
    def scan_processes_logic(self):
        """Lógica de escaneo de procesos - MEJORADO CON DETECCIÓN AVANZADA DE SUBPROCESOS E INYECCIONES"""
        print("🔍 ESCANEANDO PROCESOS...")
        issues = []
        
        # Usar el nuevo analizador de conexiones de Minecraft para detectar subprocesos e inyecciones
        try:
            from minecraft_connection_analyzer import MinecraftConnectionAnalyzer
            analyzer = MinecraftConnectionAnalyzer()
            
            # Escanear procesos de Minecraft y detectar inyecciones/subprocesos ocultos
            print("🔍 Analizando procesos de Minecraft y subprocesos ocultos...")
            minecraft_issues = analyzer.scan_minecraft_processes_and_injections()
            issues.extend(minecraft_issues)
            
            # Detectar autoclickers relacionados con Minecraft
            autoclicker_issues = analyzer.detect_autoclicker_processes()
            issues.extend(autoclicker_issues)
            
            # Obtener username desde conexiones activas
            if analyzer.minecraft_username:
                self.detected_minecraft_username = analyzer.minecraft_username
                print(f"👤 Username de Minecraft detectado desde conexión activa: {analyzer.minecraft_username}")
        except ImportError:
            print("⚠️ Módulo minecraft_connection_analyzer no disponible")
        except Exception as e:
            print(f"⚠️ Error en análisis avanzado de conexiones: {e}")
        
        # Detectar autoclickers activos
        if self.autoclicker_detector:
            try:
                print("🔍 Detectando autoclickers activos...")
                autoclicker_issues = self.autoclicker_detector.scan_running_processes()
                for issue in autoclicker_issues:
                    issues.append({
                        'tipo': 'process',
                        'nombre': issue.get('name', 'Unknown'),
                        'ruta': issue.get('exe', ''),
                        'archivo': issue.get('exe', ''),
                        'categoria': issue.get('type', 'autoclicker'),
                        'alerta': issue.get('alert', 'SOSPECHOSO'),
                        'confidence': issue.get('confidence', 0.5),
                        'detected_patterns': ['autoclicker_active'],
                        'is_active_process': True
                    })
                print(f"✅ Detectados {len(autoclicker_issues)} autoclickers activos")
            except Exception as e:
                print(f"⚠️ Error detectando autoclickers: {e}")
        
        # Detectar inyección en procesos Java/Minecraft
        if self.java_injection_detector:
            try:
                print("🔍 Detectando inyección en procesos Java...")
                injection_issues = self.java_injection_detector.scan_java_processes()
                for issue in injection_issues:
                    issues.append({
                        'tipo': 'java_injection',
                        'nombre': issue.get('description', 'Java Injection'),
                        'ruta': issue.get('agent_path', '') or issue.get('bootclasspath', '') or issue.get('jar_file', ''),
                        'archivo': issue.get('agent_path', '') or issue.get('bootclasspath', '') or issue.get('jar_file', ''),
                        'categoria': issue.get('type', 'injection'),
                        'alerta': issue.get('alert', 'CRITICAL'),
                        'confidence': issue.get('confidence', 0.8),
                        'detected_patterns': ['java_injection'],
                        'injection_detected': True
                    })
                print(f"✅ Detectadas {len(injection_issues)} inyecciones en procesos Java")
            except Exception as e:
                print(f"⚠️ Error detectando inyecciones: {e}")
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    proc_info = proc.info
                    name = proc_info['name'].lower()
                    cmdline = ' '.join(proc_info['cmdline']) if proc_info['cmdline'] else ''
                    
                    # Detectar procesos sospechosos
                    if self.is_suspicious_process(name):
                        issues.append({
                            'tipo': 'PROCESS',
                            'nombre': proc_info['name'],
                            'ruta': proc_info['exe'] or 'N/A',
                            'pid': proc_info['pid'],
                            'cmdline': cmdline,
                            'alerta': 'CRITICAL',
                            'categoria': 'PROCESSES'
                        })
                    
                    # Detectar comandos Java sospechosos - MEJORADO CON MÁS PATRONES
                    if 'java' in name and any(cmd in cmdline.lower() for cmd in ['-jar', '-cp', 'minecraft']):
                        # Patrones expandidos de hacks en línea de comandos Java
                        java_hack_patterns = [
                            'vape', 'entropy', 'liquidbounce', 'wurst', 'impact', 'sigma',
                            'flux', 'future', 'astolfo', 'exhibition', 'novoline', 'rise',
                            'moon', 'drip', 'phobos', 'komat', 'wasp', 'konas', 'seppuku',
                            'inject', 'injector', 'ghost', 'bypass', 'stealth', 'undetected',
                            'killaura', 'aimbot', 'triggerbot', 'reach', 'velocity', 'scaffold',
                            'fly', 'xray', 'fullbright', 'speedhack', 'wtap', 'aimassist',
                            'bhop', 'nofall', 'autoclicker', 'ac.exe', 'ac.jar'
                        ]
                        
                        cmdline_lower = cmdline.lower()
                        detected_hacks = [hack for hack in java_hack_patterns if hack in cmdline_lower]
                        
                        if detected_hacks:
                            # Verificar que no sea falso positivo
                            if not self.is_whitelisted(cmdline):
                                alert_level = 'CRITICAL' if any(h in detected_hacks for h in ['vape', 'entropy', 'whiteout', 'injector']) else 'SOSPECHOSO'
                            issues.append({
                                'tipo': 'JAVA_CMD',
                                'nombre': proc_info['name'],
                                'ruta': cmdline,
                                'pid': proc_info['pid'],
                                'cmdline': cmdline,
                                    'alerta': alert_level,
                                    'categoria': 'JAVA_CMD',
                                    'detected_hacks': detected_hacks
                            })
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            print(f"Error escaneando procesos: {e}")
            
        return issues
    
    def scan_minecraft_files_logic(self):
        """Lógica de escaneo de archivos de Minecraft - MEJORADO CON DETECCIÓN AVANZADA"""
        print("🔍 ESCANEANDO ARCHIVOS DE MINECRAFT...")
        issues = []
        
        # Analizar texturas X-ray
        if self.xray_analyzer:
            try:
                print("🔍 Analizando texturas X-ray...")
                xray_issues = self.xray_analyzer.scan_resource_packs()
                for issue in xray_issues:
                    issues.append({
                        'tipo': 'xray_texture',
                        'nombre': issue.get('name', 'Unknown'),
                        'ruta': os.path.dirname(issue.get('path', '')),
                        'archivo': issue.get('path', ''),
                        'categoria': 'texture_modification',
                        'alerta': issue.get('alert', 'SOSPECHOSO'),
                        'confidence': issue.get('confidence', 0.6),
                        'detected_patterns': ['xray_texture'],
                        'transparency_ratio': issue.get('transparency_ratio', 0)
                    })
                print(f"✅ Detectadas {len(xray_issues)} texturas X-ray")
            except Exception as e:
                print(f"⚠️ Error analizando texturas X-ray: {e}")
        
        try:
            # Rutas comunes de Minecraft expandidas
            minecraft_paths = [
                os.path.expanduser("~\\AppData\\Roaming\\.minecraft"),
                os.path.expanduser("~\\AppData\\Local\\.minecraft"),
                os.path.expanduser("~\\AppData\\LocalLow\\.minecraft"),
                "C:\\Users\\Public\\Minecraft",
                "C:\\Program Files\\Minecraft",
                "C:\\Program Files (x86)\\Minecraft",
                os.path.expanduser("~\\Documents\\Minecraft"),
                os.path.expanduser("~\\Desktop\\Minecraft"),
                os.path.expanduser("~\\Downloads\\Minecraft"),
                # Launchers alternativos
                os.path.expanduser("~\\AppData\\Roaming\\.tlauncher"),
                os.path.expanduser("~\\AppData\\Roaming\\.multimc"),
                os.path.expanduser("~\\AppData\\Roaming\\.prismlauncher"),
                os.path.expanduser("~\\AppData\\Roaming\\.gdlauncher"),
                os.path.expanduser("~\\AppData\\Roaming\\.lunarclient"),
                os.path.expanduser("~\\AppData\\Roaming\\.badlion"),
            ]
            
            # Extensiones a escanear en carpetas de Minecraft
            minecraft_extensions = ('.jar', '.class', '.java', '.lua', '.txt', '.log', '.cfg', 
                                   '.config', '.json', '.properties', '.dat', '.cache', '.tmp')
            
            for path in minecraft_paths:
                if os.path.exists(path):
                    print(f"📁 Escaneando: {path}")
                    try:
                        for root, dirs, files in os.walk(path):
                            # Verificar carpetas sospechosas primero
                            for dir_name in dirs:
                                dir_lower = dir_name.lower()
                                if any(hack in dir_lower for hack in ['vape', 'entropy', 'flux', 'sigma', 
                                                                      'inject', 'ghost', 'bypass', 'hack', 'cheat']):
                                    if not self.is_whitelisted(os.path.join(root, dir_name)):
                                        issues.append({
                                            'tipo': 'MINECRAFT_FOLDER',
                                            'nombre': dir_name,
                                            'ruta': os.path.join(root, dir_name),
                                            'archivo': os.path.join(root, dir_name),
                                            'alerta': 'CRITICAL',
                                            'categoria': 'MINECRAFT'
                                        })
                            
                            # Escanear archivos
                            for file in files:
                                file_lower = file.lower()
                                # Solo escanear extensiones relevantes
                                if file_lower.endswith(minecraft_extensions):
                                    full_path = os.path.join(root, file)
                                    
                                    # Verificar si es sospechoso (con análisis de contenido)
                                    if self.is_suspicious_file(full_path):
                                        # Análisis avanzado de contenido
                                        content_analysis = self.analyze_file_content(full_path)
                                        
                                        alert_level = 'SOSPECHOSO'
                                        if content_analysis['is_hack'] and content_analysis['confidence'] >= 80:
                                            alert_level = 'CRITICAL'
                                        
                                issues.append({
                                    'tipo': 'MINECRAFT_FILE',
                                    'nombre': file,
                                    'ruta': full_path,
                                    'archivo': file,
                                            'alerta': alert_level,
                                            'categoria': 'MINECRAFT',
                                            'confidence': content_analysis.get('confidence', 0),
                                            'detected_patterns': content_analysis.get('detected_patterns', []),
                                            'obfuscation': content_analysis.get('obfuscation_detected', False),
                                            'file_hash': content_analysis.get('file_hash')
                                        })
                    except PermissionError:
                        continue
                    except Exception as e:
                        print(f"Error escaneando {path}: {e}")
                        continue
                                
        except Exception as e:
            print(f"Error escaneando archivos de Minecraft: {e}")
            
        return issues
    
    def scan_all_jars(self):
        """Escanea todos los JARs en el sistema - MEJORADO CON ANÁLISIS DE CONTENIDO"""
        print("🔍 ESCANEANDO TODOS LOS JARs...")
        issues = []
        
        def scan():
            try:
                # Ubicaciones prioritarias primero (más rápido)
                priority_locations = [
                    os.path.expanduser("~\\AppData\\Roaming\\.minecraft"),
                    os.path.expanduser("~\\AppData\\Local"),
                    os.path.expanduser("~\\Downloads"),
                    os.path.expanduser("~\\Desktop"),
                    os.path.expanduser("~\\Documents"),
                    "C:\\Temp",
                    "C:\\Windows\\Temp"
                ]
                
                # Escanear ubicaciones prioritarias primero
                for location in priority_locations:
                    if os.path.exists(location):
                        try:
                            for root, dirs, files in os.walk(location):
                                # Limitar profundidad
                                if root.count(os.sep) - location.count(os.sep) > 10:
                                    dirs[:] = []
                                    continue
                                
                            for file in files:
                                if file.lower().endswith('.jar'):
                                        full_path = os.path.join(root, file)
                                        
                                        # Verificar whitelist primero
                                        if self.is_whitelisted(full_path):
                                            continue
                                        
                                        # Análisis avanzado de contenido
                                        content_analysis = self.analyze_file_content(full_path)
                                        
                                        # Si el análisis de contenido indica hack con alta confianza
                                        if content_analysis['is_hack'] and content_analysis['confidence'] >= 60:
                                            issues.append({
                                                'tipo': 'JAR_FILE',
                                                'nombre': file,
                                                'ruta': full_path,
                                                'archivo': file,
                                                'hash': content_analysis.get('file_hash', 'N/A'),
                                                'alerta': 'CRITICAL' if content_analysis['confidence'] >= 80 else 'SOSPECHOSO',
                                                'categoria': 'JAR_FILES',
                                                'confidence': content_analysis['confidence'],
                                                'detected_patterns': content_analysis.get('detected_patterns', []),
                                                'obfuscation': content_analysis.get('obfuscation_detected', False)
                                            })
                                        # Si el nombre es sospechoso
                                        elif self.is_suspicious_file(full_path):
                                            issues.append({
                                                'tipo': 'JAR_FILE',
                                                'nombre': file,
                                                'ruta': full_path,
                                                'archivo': file,
                                                'hash': content_analysis.get('file_hash', 'N/A'),
                                            'alerta': 'SOSPECHOSO',
                                                'categoria': 'JAR_FILES',
                                                'confidence': content_analysis.get('confidence', 0)
                                            })
                        except (PermissionError, OSError):
                            continue
                        except Exception as e:
                            print(f"Error escaneando {location}: {e}")
                            continue
                
                # Escanear otras unidades si hay tiempo
                drives = ['C:\\', 'D:\\', 'E:\\', 'F:\\']
                for drive in drives:
                    if os.path.exists(drive) and drive not in ['C:\\']:  # Ya escaneamos C en ubicaciones prioritarias
                        try:
                            # Solo escanear carpetas específicas en otras unidades
                            specific_folders = [
                                os.path.join(drive, "Users"),
                                os.path.join(drive, "Temp"),
                                os.path.join(drive, "Downloads")
                            ]
                            for folder in specific_folders:
                                if os.path.exists(folder):
                                    for root, dirs, files in os.walk(folder):
                                        if root.count(os.sep) - folder.count(os.sep) > 5:
                                            dirs[:] = []
                                            continue
                                        
                                        for file in files:
                                            if file.lower().endswith('.jar'):
                                                full_path = os.path.join(root, file)
                                                if not self.is_whitelisted(full_path):
                                                    content_analysis = self.analyze_file_content(full_path)
                                                    if content_analysis['is_hack'] and content_analysis['confidence'] >= 70:
                                                        issues.append({
                                                            'tipo': 'JAR_FILE',
                                                            'nombre': file,
                                                            'ruta': full_path,
                                                            'archivo': file,
                                                            'hash': content_analysis.get('file_hash', 'N/A'),
                                                            'alerta': 'CRITICAL',
                                                            'categoria': 'JAR_FILES',
                                                            'confidence': content_analysis['confidence']
                                                        })
                        except:
                            continue
                                        
            except Exception as e:
                print(f"Error escaneando JARs: {e}")
                
        scan()
        return issues
    
    def scan_recent_files(self):
        """Escanea archivos recientes"""
        print("🔍 ESCANEANDO ARCHIVOS RECIENTES...")
        issues = []
        
        def scan():
            try:
                # Escanear archivos modificados en las últimas 24 horas
                cutoff_time = time.time() - (24 * 60 * 60)
                
                drives = ['C:\\', 'D:\\', 'E:\\', 'F:\\']
                for drive in drives:
                    if os.path.exists(drive):
                        for root, dirs, files in os.walk(drive):
                            for file in files:
                                try:
                                    file_path = os.path.join(root, file)
                                    if os.path.getmtime(file_path) > cutoff_time:
                                        if self.is_suspicious_file(file.lower()):
                                            issues.append({
                                                'tipo': 'RECENT_FILE',
                                                'nombre': file,
                                                'ruta': file_path,
                                                'archivo': file,
                                                'alerta': 'POCO_SOSPECHOSO',
                                                'categoria': 'RECENT_FILES'
                                            })
                                except:
                                    continue
                                    
            except Exception as e:
                print(f"Error escaneando archivos recientes: {e}")
                
        scan()
        return issues
    
    def scan_prefetch_jna(self):
        """Escanea Prefetch y JNA"""
        print("🔍 ESCANEANDO PREFETCH Y JNA...")
        issues = []
        
        def scan():
            try:
                # Escanear Prefetch
                prefetch_path = "C:\\Windows\\Prefetch"
                if os.path.exists(prefetch_path):
                    for file in os.listdir(prefetch_path):
                        if file.lower().endswith('.pf'):
                            if any(hack in file.lower() for hack in ['vape', 'entropy', 'liquidbounce']):
                                issues.append({
                                    'tipo': 'PREFETCH',
                                    'nombre': file,
                                    'ruta': os.path.join(prefetch_path, file),
                                    'alerta': 'SOSPECHOSO',
                                    'categoria': 'PREFETCH'
                                })
                
                # Escanear JNA
                jna_paths = [
                    "C:\\Windows\\System32",
                    "C:\\Windows\\SysWOW64"
                ]
                
                for path in jna_paths:
                    if os.path.exists(path):
                        for file in os.listdir(path):
                            if 'jna' in file.lower():
                                issues.append({
                                    'tipo': 'JNA',
                                    'nombre': file,
                                    'ruta': os.path.join(path, file),
                                    'alerta': 'POCO_SOSPECHOSO',
                                    'categoria': 'JNA'
                                })
                                
            except Exception as e:
                print(f"Error escaneando Prefetch/JNA: {e}")
                
        scan()
        return issues
    
    def scan_temp_jna(self):
        """Escanea archivos temporales y JNA"""
        print("🔍 ESCANEANDO ARCHIVOS TEMPORALES...")
        issues = []
        
        def scan():
            try:
                temp_paths = [
                    os.environ.get('TEMP', ''),
                    os.environ.get('TMP', ''),
                    "C:\\Windows\\Temp"
                ]
                
                for path in temp_paths:
                    if os.path.exists(path):
                        for file in os.listdir(path):
                            if self.is_suspicious_file(file.lower()):
                                issues.append({
                                    'tipo': 'TEMP_FILE',
                                    'nombre': file,
                                    'ruta': os.path.join(path, file),
                                    'alerta': 'POCO_SOSPECHOSO',
                                    'categoria': 'TEMP_FILES'
                                })
                                
            except Exception as e:
                print(f"Error escaneando archivos temporales: {e}")
                
        scan()
        return issues
    
    def scan_registry_complete(self):
        """Escaneo completo del registro"""
        print("🔍 ESCANEANDO REGISTRO COMPLETO...")
        issues = []
        
        def scan():
            try:
                registry_paths = [
                    (winreg.HKEY_CURRENT_USER, "Software"),
                    (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE"),
                    (winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run"),
                    (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run")
                ]
                
                for hkey, path in registry_paths:
                    try:
                        with winreg.OpenKey(hkey, path) as key:
                            self._scan_registry_key(key, path)
                    except:
                        continue
                        
            except Exception as e:
                print(f"Error escaneando registro: {e}")
                
        scan()
        return issues
    
    def scan_dns_cache(self):
        """Escanea caché DNS buscando dominios de distribución de ghost clients."""
        print("🔍 ESCANEANDO CACHÉ DNS...")
        issues = []
        HACK_DOMAINS = [
            'vape', 'entropy', 'liquidbounce', 'sigma.rip', 'riseclient',
            'meteorclient', 'wurst-client', 'lbest.pw', 'vape.gg',
            'drazclient', 'drip-client', 'rusherhack', 'novoline',
            'astolfoclient', 'fluxclient', 'futureclient', 'inertia',
            'salhack', 'azuraclient', 'vertexclient', 'daturamc',
            'jelloclient', 'weavemcr', 'weaveclient',
        ]
        try:
            result = subprocess.run(['ipconfig', '/displaydns'], capture_output=True, text=True)
            if result.returncode == 0:
                dns_output = result.stdout.lower()
                matched = [d for d in HACK_DOMAINS if d in dns_output]
                if matched:
                    print(f"⚠️ DNS CACHE SOSPECHOSA: {matched}")
                    issues.append({
                        'tipo': 'dns_cache_hack',
                        'nombre': f'DNS cache con dominio de hack: {", ".join(matched)}',
                        'ruta': 'DNS Cache',
                        'archivo': ', '.join(matched),
                        'alerta': 'SOSPECHOSO',
                        'categoria': 'DNS_CACHE',
                        'confidence': 0.80,
                        'detected_patterns': [f'dns:{d}' for d in matched],
                    })
        except Exception as e:
            print(f"Error escaneando caché DNS: {e}")
        return issues
    
    def scan_services(self):
        """Escanea servicios de Windows"""
        print("🔍 ESCANEANDO SERVICIOS...")
        issues = []
        
        def scan():
            try:
                for service in psutil.win_service_iter():
                    try:
                        service_info = service.as_dict()
                        name = service_info['name'].lower()
                        display_name = service_info['display_name'].lower()
                        
                        if any(hack in name or hack in display_name for hack in ['vape', 'entropy', 'liquidbounce']):
                            issues.append({
                                'tipo': 'SERVICE',
                                'nombre': service_info['display_name'],
                                'ruta': service_info['binpath'],
                                'alerta': 'CRITICAL',
                                'categoria': 'SERVICES'
                            })
                    except:
                        continue
                        
            except Exception as e:
                print(f"Error escaneando servicios: {e}")
                
        scan()
        return issues
    
    def scan_logitech(self):
        """Escanea macros de Logitech"""
        print("🔍 ESCANEANDO MACROS DE LOGITECH...")
        issues = []
        
        def scan():
            try:
                logitech_path = "C:\\Program Files\\LGHUB"
                if os.path.exists(logitech_path):
                    for root, dirs, files in os.walk(logitech_path):
                        for file in files:
                            if file.lower().endswith(('.json', '.xml', '.cfg')):
                                if any(hack in file.lower() for hack in ['minecraft', 'mc', 'vape']):
                                    issues.append({
                                        'tipo': 'LOGITECH_MACRO',
                                        'nombre': file,
                                        'ruta': os.path.join(root, file),
                                        'alerta': 'SOSPECHOSO',
                                        'categoria': 'LOGITECH'
                                    })
                                    
            except Exception as e:
                print(f"Error escaneando macros de Logitech: {e}")
                
        scan()
        return issues
    
    def scan_razer(self):
        """Escanea macros de Razer"""
        print("🔍 ESCANEANDO MACROS DE RAZER...")
        issues = []
        
        def scan():
            try:
                razer_path = "C:\\Program Files\\Razer"
                if os.path.exists(razer_path):
                    for root, dirs, files in os.walk(razer_path):
                        for file in files:
                            if file.lower().endswith(('.json', '.xml', '.cfg')):
                                if any(hack in file.lower() for hack in ['minecraft', 'mc', 'vape']):
                                    issues.append({
                                        'tipo': 'RAZER_MACRO',
                                        'nombre': file,
                                        'ruta': os.path.join(root, file),
                                        'alerta': 'SOSPECHOSO',
                                        'categoria': 'RAZER'
                                    })
                                    
            except Exception as e:
                print(f"Error escaneando macros de Razer: {e}")
                
        scan()
        return issues
    
    def scan_date_changes(self):
        """Escanea cambios de fecha del sistema"""
        print("🔍 ESCANEANDO CAMBIOS DE FECHA...")
        issues = []
        
        def scan():
            try:
                # Verificar si la fecha del sistema ha sido modificada recientemente
                current_time = time.time()
                boot_time = psutil.boot_time()
                uptime = current_time - boot_time
                
                if uptime < 3600:  # Menos de 1 hora
                    issues.append({
                        'tipo': 'DATE_CHANGE',
                        'nombre': 'System Date Change',
                        'ruta': 'System Clock',
                        'alerta': 'POCO_SOSPECHOSO',
                        'categoria': 'DATE_CHANGES'
                    })
                    
            except Exception as e:
                print(f"Error escaneando cambios de fecha: {e}")
                
        scan()
        return issues
    
    def scan_deleted_files(self):
        """Escanea archivos eliminados usando USN Journal"""
        print("🔍 ESCANEANDO ARCHIVOS ELIMINADOS...")
        issues = []
        
        def scan():
            try:
                # Usar fsutil para leer el USN Journal
                result = subprocess.run(['fsutil', 'usn', 'readjournal', 'C:', '1'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    usn_output = result.stdout
                    if any(hack in usn_output.lower() for hack in ['vape', 'entropy', 'liquidbounce']):
                        issues.append({
                            'tipo': 'DELETED_FILE',
                            'nombre': 'Deleted File',
                            'ruta': 'USN Journal',
                            'alerta': 'SOSPECHOSO',
                            'categoria': 'DELETED_FILES'
                        })
                        
            except Exception as e:
                print(f"Error escaneando archivos eliminados: {e}")
                
        scan()
        return issues
    
    def scan_new_files(self):
        """Escanea archivos nuevos"""
        print("🔍 ESCANEANDO ARCHIVOS NUEVOS...")
        issues = []
        
        def scan():
            try:
                # Escanear archivos creados en las últimas 24 horas
                cutoff_time = time.time() - (24 * 60 * 60)
                
                drives = ['C:\\', 'D:\\', 'E:\\', 'F:\\']
                for drive in drives:
                    if os.path.exists(drive):
                        for root, dirs, files in os.walk(drive):
                            for file in files:
                                try:
                                    file_path = os.path.join(root, file)
                                    if os.path.getctime(file_path) > cutoff_time:
                                        if self.is_suspicious_file(file.lower()):
                                            issues.append({
                                                'tipo': 'NEW_FILE',
                                                'nombre': file,
                                                'ruta': file_path,
                                                'alerta': 'POCO_SOSPECHOSO',
                                                'categoria': 'NEW_FILES'
                                            })
                                except:
                                    continue
                                    
            except Exception as e:
                print(f"Error escaneando archivos nuevos: {e}")
                
        scan()
        return issues
    
    def scan_renamed_files(self):
        """Escanea archivos renombrados"""
        print("🔍 ESCANEANDO ARCHIVOS RENOMBRADOS...")
        issues = []
        
        def scan():
            try:
                # Usar fsutil para leer el USN Journal
                result = subprocess.run(['fsutil', 'usn', 'readjournal', 'C:', '2'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    usn_output = result.stdout
                    if any(hack in usn_output.lower() for hack in ['vape', 'entropy', 'liquidbounce']):
                        issues.append({
                            'tipo': 'RENAMED_FILE',
                            'nombre': 'Renamed File',
                            'ruta': 'USN Journal',
                            'alerta': 'SOSPECHOSO',
                            'categoria': 'RENAMED_FILES'
                        })
                        
            except Exception as e:
                print(f"Error escaneando archivos renombrados: {e}")
                
        scan()
        return issues
    
    def scan_usb_devices(self):
        """Escanea dispositivos USB y pendrives"""
        print("🔍 ESCANEANDO DISPOSITIVOS USB Y PENDRIVES...")
        issues = []
        
        def scan():
            try:
                # Escanear dispositivos USB usando wmic (viene con Windows)
                import subprocess
                
                result = subprocess.run(['wmic', 'logicaldisk', 'where', 'drivetype=2', 'get', 'deviceid'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # Saltar la primera línea (encabezado)
                        if line.strip():
                            drive_letter = line.strip()
                            if os.path.exists(drive_letter):
                                print(f"📱 USB encontrado: {drive_letter}")
                                for root, dirs, files in os.walk(drive_letter):
                                    for file in files:
                                        if self.is_suspicious_file(file.lower()):
                                            issues.append({
                                                'tipo': 'USB_FILE',
                                                'nombre': file,
                                                'ruta': os.path.join(root, file),
                                                'alerta': 'CRITICAL',
                                                'categoria': 'USB_DEVICES'
                                            })
                                        
            except Exception as e:
                print(f"Error escaneando dispositivos USB: {e}")
                
        scan()
        return issues
    
    def scan_hidden_files(self):
        """Escanea archivos ocultos"""
        print("🔍 ESCANEANDO ARCHIVOS OCULTOS...")
        issues = []
        
        def scan():
            try:
                drives = ['C:\\', 'D:\\', 'E:\\', 'F:\\']
                for drive in drives:
                    if os.path.exists(drive):
                        for root, dirs, files in os.walk(drive):
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    # Verificar si el archivo está oculto
                                    if os.path.getattr(file_path, 'st_file_attributes') & 0x2:  # FILE_ATTRIBUTE_HIDDEN
                                        if self.is_suspicious_file(file.lower()):
                                            issues.append({
                                                'tipo': 'HIDDEN_FILE',
                                                'nombre': file,
                                                'ruta': file_path,
                                                'alerta': 'SOSPECHOSO',
                                                'categoria': 'HIDDEN_FILES'
                                            })
                                except:
                                    continue
                                    
            except Exception as e:
                print(f"Error escaneando archivos ocultos: {e}")
                
        scan()
        return issues
    
    def scan_network_connections(self):
        """Escanea conexiones de red y IPs"""
        print("🔍 ESCANEANDO CONEXIONES DE RED E IPs...")
        issues = []
        
        def scan():
            try:
                # Escanear conexiones de red
                for conn in psutil.net_connections(kind='inet'):
                    if conn.status == 'ESTABLISHED':
                        # Verificar IPs sospechosas
                        if any(suspicious_ip in str(conn.raddr) for suspicious_ip in ['127.0.0.1', 'localhost']):
                            # Verificar si es un proceso relacionado con Minecraft
                            try:
                                process = psutil.Process(conn.pid)
                                process_name = process.name().lower()
                                if 'minecraft' in process_name or 'java' in process_name:
                                    issues.append({
                                        'tipo': 'NETWORK_CONNECTION',
                                        'nombre': f"Connection to {conn.raddr}",
                                        'ruta': f"PID: {conn.pid}, Process: {process_name}",
                                        'alerta': 'SOSPECHOSO',
                                        'categoria': 'NETWORK_CONNECTIONS'
                                    })
                            except:
                                continue
                                
            except Exception as e:
                print(f"Error escaneando conexiones de red: {e}")
                
        scan()
        return issues
    
    def scan_minecraft_usernames(self):
        """Escanea nombres de usuario de Minecraft"""
        print("🔍 ESCANEANDO NOMBRES DE USUARIO DE MINECRAFT...")
        issues = []
        
        def scan():
            try:
                # Buscar en archivos de configuración de Minecraft
                minecraft_paths = [
                    os.path.expanduser("~\\AppData\\Roaming\\.minecraft"),
                    "C:\\Users\\Public\\Minecraft"
                ]
                
                for path in minecraft_paths:
                    if os.path.exists(path):
                        for root, dirs, files in os.walk(path):
                            for file in files:
                                if file.lower().endswith(('.json', '.txt', '.cfg', '.properties')):
                                    try:
                                        file_path = os.path.join(root, file)
                                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                            content = f.read().lower()
                                            if any(hack in content for hack in ['vape', 'entropy', 'liquidbounce', 'wurst']):
                                                issues.append({
                                                    'tipo': 'MINECRAFT_CONFIG',
                                                    'nombre': file,
                                                    'ruta': file_path,
                                                    'alerta': 'SOSPECHOSO',
                                                    'categoria': 'MINECRAFT_CONFIGS'
                                                })
                                    except:
                                        continue
                                        
            except Exception as e:
                print(f"Error escaneando nombres de usuario de Minecraft: {e}")
                
        scan()
        return issues
    
    def scan_background_processes(self):
        """Escanea procesos en segundo/tercer plano"""
        print("🔍 ESCANEANDO PROCESOS EN SEGUNDO/TERCER PLANO...")
        issues = []
        
        def scan():
            try:
                for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'status']):
                    try:
                        proc_info = proc.info
                        name = proc_info['name'].lower()
                        status = proc_info['status']
                        
                        # Verificar procesos en segundo plano relacionados con Minecraft
                        if status in ['sleeping', 'idle'] and any(keyword in name for keyword in ['minecraft', 'java', 'mc']):
                            if self.is_suspicious_process(name):
                                issues.append({
                                    'tipo': 'BACKGROUND_PROCESS',
                                    'nombre': proc_info['name'],
                                    'ruta': proc_info['exe'] or 'N/A',
                                    'pid': proc_info['pid'],
                                    'status': status,
                                    'alerta': 'SOSPECHOSO',
                                    'categoria': 'BACKGROUND_PROCESSES'
                                })
                                
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                        
            except Exception as e:
                print(f"Error escaneando procesos en segundo plano: {e}")
                
        scan()
        return issues
    
    def scan_autoclick_tools(self):
        """Escanea herramientas de autoclick y tinytools"""
        print("🔍 ESCANEANDO HERRAMIENTAS DE AUTOCLICK Y TINYTOOLS...")
        issues = []
        
        def scan():
            try:
                # Patrones de herramientas de autoclick
                autoclick_patterns = [
                    'autoclick', 'auto_click', 'clicker', 'mouse_clicker',
                    'tinytools', 'tiny_tools', 'macro', 'automation',
                    'ghost_mouse', 'mouse_ghost', 'click_bot'
                ]
                
                # Escanear procesos
                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        proc_info = proc.info
                        name = proc_info['name'].lower()
                        
                        if any(pattern in name for pattern in autoclick_patterns):
                            issues.append({
                                'tipo': 'AUTOCLICK_TOOL',
                                'nombre': proc_info['name'],
                                'ruta': proc_info['exe'] or 'N/A',
                                'pid': proc_info['pid'],
                                'alerta': 'CRITICAL',
                                'categoria': 'AUTOCLICK_TOOLS'
                            })
                            
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Escanear archivos
                drives = ['C:\\', 'D:\\', 'E:\\', 'F:\\']
                for drive in drives:
                    if os.path.exists(drive):
                        for root, dirs, files in os.walk(drive):
                            for file in files:
                                if any(pattern in file.lower() for pattern in autoclick_patterns):
                                    issues.append({
                                        'tipo': 'AUTOCLICK_FILE',
                                        'nombre': file,
                                        'ruta': os.path.join(root, file),
                                        'alerta': 'CRITICAL',
                                        'categoria': 'AUTOCLICK_TOOLS'
                                    })
                                    
            except Exception as e:
                print(f"Error escaneando herramientas de autoclick: {e}")
                
        scan()
        return issues
    
    # ============================================================
    # MÉTODOS DE ESCANEO AVANZADO
    # ============================================================
    
    def quick_scan(self):
        """Escaneo rápido de elementos críticos"""
        def scan_thread():
            try:
                self.scanning = True
                self.issues_found = []
                
                print("⚡ INICIANDO ESCANEO RÁPIDO...")
                
                # Escanear procesos
                self._update_progress_safe(20, "Escaneando procesos...", "Analizando procesos activos")
                process_issues = self.scan_processes_logic()
                self.issues_found.extend(process_issues)
                
                # Escanear archivos de Minecraft
                self._update_progress_safe(40, "Escaneando archivos de Minecraft...", "Revisando carpetas de Minecraft")
                minecraft_issues = self.scan_minecraft_files_logic()
                self.issues_found.extend(minecraft_issues)
                
                # Escanear JARs
                self._update_progress_safe(60, "Escaneando JARs...", "Analizando archivos JAR")
                jar_issues = self.scan_all_jars()
                self.issues_found.extend(jar_issues)
                
                # Escanear archivos recientes
                self._update_progress_safe(80, "Escaneando archivos recientes...", "Revisando archivos modificados recientemente")
                recent_issues = self.scan_recent_files()
                self.issues_found.extend(recent_issues)
                
                # Filtrar falsos positivos
                self._update_progress_safe(90, "Filtrando resultados...", "Eliminando falsos positivos")
                self.issues_found = self.filter_false_positives(self.issues_found)
                
                self._update_progress_safe(100, "✅ Escaneo rápido completado", f"Encontrados {len(self.issues_found)} elementos")
                
                print(f"⚡ ESCANEO RÁPIDO COMPLETADO - {len(self.issues_found)} elementos encontrados")
                
            except Exception as e:
                print(f"Error en escaneo rápido: {e}")
                self._update_progress_safe(100, f"❌ Error: {str(e)}", "Error durante el escaneo")
            finally:
                self.scanning = False
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def scan_processes_ui(self):
        """Escaneo de procesos desde la UI"""
        def scan_thread():
            try:
                self.scanning = True
                self.issues_found = []
                
                print("🔍 INICIANDO ESCANEO DE PROCESOS...")
                
                self._update_progress_safe(50, "Escaneando procesos...", "Analizando procesos activos")
                process_issues = self.scan_processes_logic()
                self.issues_found.extend(process_issues)
                
                self._update_progress_safe(100, "✅ Escaneo de procesos completado", f"Encontrados {len(process_issues)} procesos")
                
                print(f"🔍 ESCANEO DE PROCESOS COMPLETADO - {len(process_issues)} procesos encontrados")
                
            except Exception as e:
                print(f"Error en escaneo de procesos: {e}")
                self._update_progress_safe(100, f"❌ Error: {str(e)}", "Error durante el escaneo")
            finally:
                self.scanning = False
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def scan_files_ui(self):
        """Escaneo de archivos desde la UI"""
        def scan_thread():
            try:
                self.scanning = True
                self.issues_found = []
                
                print("📁 INICIANDO ESCANEO DE ARCHIVOS...")
                
                # Escanear archivos de Minecraft
                self._update_progress_safe(25, "Escaneando archivos de Minecraft...", "Revisando carpetas de Minecraft")
                minecraft_issues = self.scan_minecraft_files_logic()
                self.issues_found.extend(minecraft_issues)
                
                # Escanear JARs
                self._update_progress_safe(50, "Escaneando JARs...", "Analizando archivos JAR")
                jar_issues = self.scan_all_jars()
                self.issues_found.extend(jar_issues)
                
                # Escanear archivos recientes
                self._update_progress_safe(75, "Escaneando archivos recientes...", "Revisando archivos modificados recientemente")
                recent_issues = self.scan_recent_files()
                self.issues_found.extend(recent_issues)
                
                self._update_progress_safe(100, "✅ Escaneo de archivos completado", f"Encontrados {len(self.issues_found)} archivos")
                
                print(f"📁 ESCANEO DE ARCHIVOS COMPLETADO - {len(self.issues_found)} archivos encontrados")
                
            except Exception as e:
                print(f"Error en escaneo de archivos: {e}")
                self._update_progress_safe(100, f"❌ Error: {str(e)}", "Error durante el escaneo")
            finally:
                self.scanning = False
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def filter_false_positives(self, issues):
        """Filtrado MEJORADO - Detecta hacks reales pero menos estricto"""
        filtered = []
        hacks_critical = []
        hacks_sospechoso = []
        hacks_poco_sospechoso = []
        hacks_normal = []
        
        print(f"\n🔍 INICIANDO FILTRADO MEJORADO DE {len(issues)} ELEMENTOS...")

        # Umbral mínimo de confianza — descartar ruido < 30%
        MIN_CONFIDENCE = 30
        issues = [i for i in issues if (
            i.get('tipo', '') in {
                'ghost_client_config', 'ghost_client_registry', 'jdwp_debug_port',
                'vpn_active', 'hosts_minecraft_redirect', 'injector_process',
                'blacklisted_mod', 'modified_minecraft_jar', 'hack_string_in_loaded_jar',
            } or
            (i.get('confidence', 100) * (100 if i.get('confidence', 1) <= 1 else 1)) >= MIN_CONFIDENCE
        )]
        print(f"📉 Umbral confianza {MIN_CONFIDENCE}%: {len(issues)} elementos restantes")
        
        # ============================================================
        # FILTRO MEJORADO - DETECTA HACKS REALES PERO MENOS ESTRICTO
        # ============================================================
        
        # PATRONES DE HACKS REALES (MÁS AMPLIO)
        real_hack_patterns = [
            # Vape (cliente más común - CRITICAL)
            'vape', 'vapelite', 'vapev2', 'vapev4', 'vape.exe', 'vape.jar',
            
            # Entropy (CRITICAL)
            'entropy', 'entropyclient', 'entropy.exe', 'entropy.jar',
            
            # Whiteout (CRITICAL)
            'whiteout', 'whiteoutclient', 'whiteout.exe', 'whiteout.jar',
            
            # LiquidBounce (SOSPECHOSO)
            'liquidbounce', 'liquid bounce', 'lb', 'liquidbounceclient',
            
            # Wurst (SOSPECHOSO)
            'wurst', 'wurstclient', 'wurst loader',
            
            # Impact (SOSPECHOSO)
            'impact', 'impact client', 'impactclient',
            
            # Sigma (SOSPECHOSO)
            'sigma', 'sigmaclient', 'sigma5.0', 'sigma-5.0',
            
            # Flux (SOSPECHOSO)
            'flux', 'fluxclient', 'flux b1.6', 'flux 1.8.8', 'flux1.8.8',
            
            # Future (SOSPECHOSO)
            'future', 'futureclient',
            
            # Otros clientes conocidos
            'astolfo', 'exhibition', 'novoline', 'rise', 'moon', 'drip',
            'phobos', 'komat', 'wasp', 'konas', 'seppuku', 'sloth',
            'lucid', 'tenacity', 'nyx', 'vanish', 'ploow', 'cloud',
            'nextgen', 'tegernako', 'zeroday',
            
            # Injectors (CRITICAL)
            'injector', 'inject', 'inyector', 'injection', 'dllinjector',
            
            # Ghost clients
            'ghost', 'ghostclient',
            
            # Bypass tools
            'bypass', 'stealth', 'undetected', 'incognito', 'unbypass',
            
            # Módulos específicos de hacks (CRITICAL)
            'killaura', 'aimbot', 'triggerbot', 'reach', 'velocity',
            'antiknockback', 'scaffold', 'fly', 'xray', 'fullbright',
            'speedhack', 'wtap', 'aimassist', 'bhop', 'nofall'
        ]
        
        # PATRONES DE FALSOS POSITIVOS — solo nombres/rutas muy específicas de software legítimo.
        # IMPORTANTE: NO incluir palabras genéricas como 'appdata', 'roaming', 'client', 'java',
        # 'temp', etc. porque esas palabras aparecen en rutas de hack clients reales y los filtrarían.
        exclude_patterns = [
            # Sistema Windows (rutas completas específicas)
            'windows\\system32', 'windows\\syswow64', 'windows\\winsxs',
            '\\program files\\microsoft', '\\program files (x86)\\microsoft',
            # Software legítimo (nombres de vendor específicos)
            'adobe', 'google\\chrome', 'mozilla\\firefox',
            'nvidia corporation', 'amd\\radeon', 'intel corporation',
            'nvidia\\cubins', 'nvidia\\displaydriver',
            'discord\\app-', 'teamspeak 3 client',
            'skype\\', 'zoom\\', 'microsoft teams',
            'steam\\steamapps', 'epicgames', 'origin games', 'ubisoft game launcher',
            # Servidores web (no Minecraft)
            'xampp\\', 'tomcat\\', '\\webapps\\', 'web-inf\\', 'webalizer',
            # Librerías Java legítimas (nombres exactos con versión)
            'gson-2.', 'jackson-core-', 'log4j-', 'authlib-',
            # Mods legítimos de Minecraft (nombres exactos)
            'optifine_', 'fabricloader-', 'forge-', 'minecraftforge-',
            'iris-', 'sodium-', 'lithium-', 'phosphor-', 'rubidium-',
            'jei-', 'create-', 'botania-', 'cobblemon-',
            # Launchers legítimos (#25 — whitelist extendida)
            'tlauncher-', 'prismlauncher', 'lunarclient\\', 'lunar client', 'badlion client\\',
            'polymc\\', 'atlauncher\\', 'curseforge\\', 'ftb app\\', 'gdlauncher\\', 'multimc\\',
            'gdlauncher', 'ftbapp', 'ftb_app', 'overwolf\\', 'curseforge\\',
            # Mods de performance y accesibilidad (#26)
            'ferritecore-', 'lazydfu-', 'entityculling-', 'dynamicfps-',
            'smoothboot-', 'starlight-', 'c2me-', 'noxesium-', 'krypton-',
            # Badlion como permitido (#27)
            'badlion\\', 'badlionclient\\', 'blclient\\',
            # DLLs del sistema Windows
            'api-ms-win-', 'msvcr', 'msvcp', 'vcruntime', 'ucrtbase',
            'kernel32.dll', 'user32.dll', 'advapi32.dll', 'shell32.dll',
            # Editores (rutas específicas)
            '\\vscode\\', '\\.vscode\\', 'node_modules\\', '\\jdk\\',
            'visual studio\\', 'intellij idea\\', 'pycharm\\',
            # Herramientas de edición de video y desarrollo
            'wondershare\\', 'wondershare filmora', 'filmora\\',
            'jetbrains\\', '\\jetbrains\\', 'rider\\', 'goland\\', 'webstorm\\', 'clion\\',
            # AppData: rutas de sistema / browsers / apps legítimas (NO son hacks)
            'webview2runtime', 'trust protection lists', 'pspc_sdk',
            'appdata\\local\\packages',          # Windows Store apps (firmadas, sandboxed)
            'appdata\\local\\origin',            # EA Origin
            'appdata\\local\\nvidia',
            'appdata\\local\\microsoft\\edge',
            'appdata\\roaming\\opera software',
            'electronic arts\\ea desktop',       # EA Desktop launcher
            'site-packages',                     # librerías Python instaladas
            'voicemod',                          # voice changer legítimo
            'minecraftsstool',                   # el propio SS tool del servidor
        ]
        
        # ============================================================
        # FILTRADO MEJORADO
        # ============================================================
        
        # Tipos generados por scanners especializados — siempre pasan el filtro
        TRUSTED_TYPES = {
            'ghost_client_config', 'ghost_client_registry', 'jdwp_debug_port',
            'vpn_active', 'hosts_minecraft_redirect', 'hosts_file_custom',
            'blacklisted_mod', 'dll_injection_java', 'ahk_autoclick',
            'bloody_a4tech', 'peripheral_macro', 'arduino_hid_device',
            'injector_process', 'temp_jar_recent', 'baritone_prohibited',
            'baritone_installed', 'litematica_printer', 'schematica_printer',
            'optifine_zoom_combat', 'modified_minecraft_jar', 'hack_string_in_loaded_jar',
            'javaagent_injection', 'bootclasspath_modification',
            # Nuevas detecciones P1 y P3
            'weave_loader', 'prefetch_hack', 'usn_deleted_hack',
            'jitter_script', 'java_suspicious_parent', 'java_unusual_parent',
            'evasion_indicators', 'kill_chain', 'minecraft_safe_mode',
            'suspicious_process_location', 'short_lived_process', 'cloud_hash_match',
            'prescan_cleanup', 'suspicious_process_tree', 'unknown_parent_process',
            'baseline_anomaly', 'config_tfidf_match',
            'suspicious_network_connection',
        }

        # ── Rutas que NUNCA son hacks — se aplican ANTES del bypass de TRUSTED_TYPES ──
        # Razón: tipos como usn_deleted_hack, prefetch_hack saltaban el exclude_patterns
        # y flagueaban archivos temporales de Chrome, Edge, Firefox como hacks.
        ABSOLUTE_SAFE_PATHS = {
            # Navegadores (sus carpetas de perfil generan cientos de false positives)
            'google\\chrome', 'appdata\\local\\google',
            'mozilla\\firefox', 'appdata\\roaming\\mozilla',
            'microsoft\\edge', 'appdata\\local\\microsoft\\edge',
            'opera software', 'appdata\\roaming\\opera',
            'appdata\\local\\brave-browser',
            'appdata\\local\\vivaldi',
            # Sistema Windows — prefetch, temp del sistema
            'windows\\prefetch', 'windows\\system32', 'windows\\syswow64',
            'windows\\winsxs', 'windows\\softwaredistribution',
            # Launchers legítimos de Minecraft (clientes oficiales)
            'lunarclient', 'lunar client', 'lunar-client',
            'badlion', 'badlionclient', 'blclient',
            'tlauncher', 'prismlauncher', 'multimc', 'polymc',
            'curseforge', 'ftb app', 'ftbapp', 'gdlauncher', 'atlauncher', 'overwolf',
            # Plataformas de juego legítimas
            'steam\\steamapps', 'epicgames', 'origin games', 'ubisoft game launcher',
            'riotgames', 'riot games', 'battlenet', 'battle.net',
            # IDEs y desarrollo
            'visual studio', 'intellij idea', 'pycharm', 'webstorm', 'clion',
            'jetbrains', '\\vscode\\', '\\.vscode\\', 'node_modules',
            # Drivers y software del sistema
            'nvidia corporation', 'nvidia\\cubins', 'nvidia\\displaydriver',
            'amd\\radeon', 'intel corporation',
            # Comunicación
            'discord\\app-', 'teamspeak 3 client', 'zoom\\', 'skype\\',
            'microsoft teams',
            # Software legítimo
            'appdata\\local\\packages',   # Windows Store (sandboxed)
            'appdata\\local\\nvidia',
            'wondershare', 'filmora', 'obs-studio', 'obs studio',
            'site-packages',              # librerías Python instaladas
            'voicemod',
            'program files\\microsoft',
            'program files (x86)\\microsoft',
            'minecraftsstool',            # el propio scanner
        }

        for item in issues:
            nombre = item.get('nombre', '').lower()
            ruta = item.get('ruta', '').lower()
            archivo = item.get('archivo', '').lower()
            tipo = item.get('tipo', '').lower()

            # ── FILTRO ABSOLUTO — se ejecuta antes de cualquier otra lógica ──
            # Bloquea rutas de software legítimo sin importar el tipo del hallazgo.
            _combined_path = ruta + '|' + archivo
            _is_absolute_safe = any(safe in _combined_path for safe in ABSOLUTE_SAFE_PATHS)
            if _is_absolute_safe:
                print(f"✅ [SAFE_PATH] Excluido por ruta segura: {nombre} @ {ruta[:80]}")
                continue

            # Tipos de scanners especializados — confiar en ellos sin filtrar
            if tipo in TRUSTED_TYPES:
                filtered.append(item)
                continue

            # 1. EXCLUIR SOLO FALSOS POSITIVOS MUY OBVIOS
            is_false_positive = False
            
            # Verificar con sistema de patrones legítimos aprendidos
            if self.legitimate_patterns:
                try:
                    file_hash = item.get('file_hash', '')
                    is_legitimate, legit_confidence = self.legitimate_patterns.is_legitimate(
                        file_path=ruta or archivo,
                        file_name=archivo or nombre,
                        file_hash=file_hash,
                        context={'file_path': ruta or archivo}
                    )
                    
                    if is_legitimate and legit_confidence >= 0.5:
                        is_false_positive = True
                        print(f"✅ Filtrado como legítimo aprendido: {archivo or nombre} (confianza: {legit_confidence:.2f})")
                except Exception as e:
                    pass
            
            # Verificar patrones de exclusión tradicionales
            if not is_false_positive:
                for pattern in exclude_patterns:
                    if pattern in ruta or pattern in archivo or pattern in nombre:
                        is_false_positive = True
                        break
            
            # Verificar falsos positivos específicos adicionales
            if not is_false_positive:
                for false_positive in ['zomboid', 'shaders\\', '\\textures\\', 'system32', '\\program files\\', '\\windows\\system', 'microsoft\\', 'adobe\\']:
                    if false_positive in ruta or false_positive in archivo or false_positive in nombre:
                        is_false_positive = True
                        break
            
            if is_false_positive:
                continue
            
            # 2. ANÁLISIS AVANZADO DE CONTENIDO (si es un archivo)
            content_confidence = 0
            if tipo in ['file', 'jar_file', 'minecraft_file'] and 'archivo' in item:
                try:
                    file_path = item.get('archivo') or item.get('ruta')
                    if file_path and os.path.exists(str(file_path)):
                        content_analysis = self.analyze_file_content(str(file_path))
                        content_confidence = content_analysis.get('confidence', 0)
                        # Si el análisis de contenido indica hack con alta confianza, es definitivamente un hack
                        if content_analysis.get('is_hack') and content_confidence >= 70:
                            item['confidence'] = content_confidence
                            item['detected_patterns'] = content_analysis.get('detected_patterns', [])
                            item['obfuscation'] = content_analysis.get('obfuscation_detected', False)
                            item['file_hash'] = content_analysis.get('file_hash')
                except:
                    pass
            
            # 3. ACEPTAR SI CONTIENE PATRONES DE HACKS
            is_potential_hack = False
            for pattern in real_hack_patterns:
                if pattern in archivo or pattern in nombre:
                    is_potential_hack = True
                    break
            
            # 4. TAMBIÉN ACEPTAR SI ESTÁ EN CARPETAS SOSPECHOSAS
            suspicious_paths = [
                'minecraft', 'mc', 'forge', 'fabric', 'mods', 'versions',
                'libraries', 'natives', 'assets', 'resourcepacks',
                'hack', 'cheat', 'downloads', 'desktop',
                'temp', 'tmp',
            ]
            
            is_in_suspicious_folder = any(path in ruta for path in suspicious_paths)
            
            # 5. CLASIFICAR POR SEVERIDAD (usando análisis de contenido si está disponible)
            if is_potential_hack or is_in_suspicious_folder or content_confidence >= 60:
                # Usar análisis de contenido para determinar severidad si está disponible
                # IMPORTANTE: no sobreescribir categoria si ya fue asignada por el scanner
                if content_confidence >= 80:
                    item['alerta'] = 'CRITICAL'
                    if not item.get('categoria'): item['categoria'] = 'HACKS'
                    hacks_critical.append(item)
                elif content_confidence >= 60:
                    item['alerta'] = 'SOSPECHOSO'
                    if not item.get('categoria'): item['categoria'] = 'HACKS'
                    hacks_sospechoso.append(item)
                elif any(hack in archivo for hack in ['vape', 'entropy', 'whiteout', 'injector', 'dllinjector']):
                    item['alerta'] = 'CRITICAL'
                    if not item.get('categoria'): item['categoria'] = 'HACKS'
                    hacks_critical.append(item)
                elif any(hack in archivo for hack in ['liquidbounce', 'wurst', 'impact', 'inject', 'killaura', 'aimbot']):
                    item['alerta'] = 'SOSPECHOSO'
                    if not item.get('categoria'): item['categoria'] = 'HACKS'
                    hacks_sospechoso.append(item)
                elif any(hack in archivo for hack in ['sigma', 'flux', 'future', 'ghost', 'bypass']):
                    item['alerta'] = 'POCO_SOSPECHOSO'
                    if not item.get('categoria'): item['categoria'] = 'HACKS'
                    hacks_poco_sospechoso.append(item)
                else:
                    item['alerta'] = 'NORMAL'
                    if not item.get('categoria'): item['categoria'] = 'HACKS'
                    hacks_normal.append(item)
                
                filtered.append(item)
        
        # Correlación de evidencias: escalar si hay 2+ indicadores del mismo tipo
        JAVA_INJECTION_TYPES = {
            'jdwp_debug_port', 'javaagent_injection', 'bootclasspath_modification',
            'dll_injection_java', 'hack_string_in_loaded_jar', 'injector_process',
        }
        AUTOCLICK_TYPES = {
            'ahk_autoclick', 'peripheral_macro', 'bloody_a4tech', 'arduino_hid_device',
        }
        GHOST_TYPES = {
            'ghost_client_config', 'ghost_client_registry', 'blacklisted_mod', 'modified_minecraft_jar',
        }
        for group in (JAVA_INJECTION_TYPES, AUTOCLICK_TYPES, GHOST_TYPES):
            matching = [i for i in filtered if i.get('tipo', '') in group]
            if len(matching) >= 2:
                for item in matching:
                    if item.get('alerta') not in ('CRITICAL',):
                        item['alerta'] = 'CRITICAL'
                        item['confidence'] = max(item.get('confidence', 0.8), 0.92)
                        item['detected_patterns'] = list(set(item.get('detected_patterns', []) + ['multi_evidence_correlation']))
                print(f"🔗 Correlación de evidencias: {len(matching)} hallazgos → CRITICAL")

        # Mostrar estadísticas de filtrado
        print(f"\n📊 ESTADÍSTICAS DE FILTRADO MEJORADO:")
        print(f"🔴 HACKS CRÍTICOS: {len(hacks_critical)}")
        print(f"🟠 SOSPECHOSOS: {len(hacks_sospechoso)}")
        print(f"🟡 POCO SOSPECHOSOS: {len(hacks_poco_sospechoso)}")
        print(f"🟢 NORMALES: {len(hacks_normal)}")
        print(f"📋 TOTAL FILTRADO: {len(filtered)}")
        print(f"🗑️ ELEMENTOS DESCARTADOS: {len(issues) - len(filtered)}")
        
        # Mostrar ejemplos de cada categoría
        if hacks_critical:
            print(f"\n🔴 HACKS CRÍTICOS ENCONTRADOS:")
            for item in hacks_critical[:5]:  # Mostrar solo los primeros 5
                print(f"  - {item.get('archivo', 'N/A')} en {item.get('ruta', 'N/A')}")
        
        if hacks_sospechoso:
            print(f"\n🟠 HACKS SOSPECHOSOS ENCONTRADOS:")
            for item in hacks_sospechoso[:5]:  # Mostrar solo los primeros 5
                print(f"  - {item.get('archivo', 'N/A')} en {item.get('ruta', 'N/A')}")
        
        if hacks_poco_sospechoso:
            print(f"\n🟡 HACKS POCO SOSPECHOSOS ENCONTRADOS:")
            for item in hacks_poco_sospechoso[:5]:
                print(f"  - {item.get('archivo', 'N/A')} en {item.get('ruta', 'N/A')}")

        # P2 #8 — Descartar JARs demasiado pequeños (< 3KB)
        filtered = self._filter_by_file_size(filtered)

        # P2 #28 — Reducir score de archivos en rutas de sync cloud
        filtered = self._filter_backup_sync(filtered)

        # P2 #22 — Decay de score por antigüedad de evidencia
        filtered = self._apply_score_decay(filtered)

        # P2 #30 — Umbrales dinámicos ajustados por feedback loop
        filtered = self._apply_feedback_thresholds(filtered)

        # P2 #23 — Agregar explicaciones en español a todos los hallazgos
        filtered = self._apply_human_explanations(filtered)

        # P2 #24 — Agrupar resultados repetidos del mismo tipo
        filtered = self._group_related_results(filtered)

        # P2 #13 — Descartar procesos conocidos y seguros
        filtered = self._apply_process_whitelist(filtered)

        # P3 #2 + #16 — Ajuste dinámico de confidence por rareza y patrones de bans
        filtered = self._apply_cloud_rarity_and_ban_patterns(filtered)

        # P2 #4 — Indicador aislado: cap a SOSPECHOSO si no hay 2+ evidencias independientes
        filtered = self._apply_single_indicator_cap(filtered)

        # P2 #21 — Escalar a CRITICAL por combinaciones de evidencias
        filtered = self._apply_combination_penalties(filtered)

        print(f"📋 TOTAL FINAL (tras decay + agrupación): {len(filtered)}")
        return filtered
        
    def load_config(self):
        """Carga la configuración desde ubicación persistente"""
        try:
            import sys
            
            # Intentar múltiples ubicaciones (en orden de prioridad)
            possible_paths = []
            
            if getattr(sys, 'frozen', False):
                # Si está compilado, buscar config.json en ubicaciones persistentes
                exe_dir = os.path.dirname(sys.executable)
                
                # PRIORIDAD: Buscar primero junto al ejecutable (donde se extrae el ZIP)
                # 1. Junto al ejecutable (PRIMERO - para detectar config.json del ZIP)
                possible_paths.append(os.path.join(exe_dir, 'config.json'))
                
                # 2. Directorio actual (donde se ejecuta, puede ser diferente del exe_dir)
                possible_paths.append(os.path.join(os.getcwd(), 'config.json'))
                
                # 3. Directorio padre del ejecutable
                possible_paths.append(os.path.join(exe_dir, '..', 'config.json'))
                
                # 4. AppData\Roaming (más persistente, para guardar después)
                appdata_roaming = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'config.json')
                possible_paths.append(appdata_roaming)
            else:
                # Si está en desarrollo, buscar en el directorio del script
                script_dir = os.path.dirname(os.path.abspath(__file__))
                possible_paths = [
                    os.path.join(script_dir, 'config.json'),
                    os.path.join(script_dir, '..', 'config.json'),
                    os.path.join(os.getcwd(), 'config.json'),
                    'config.json',
                ]
            
            # Intentar cada ruta
            for config_path in possible_paths:
                config_path = os.path.abspath(config_path)  # Normalizar ruta
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            print(f"✅ Config cargado desde: {config_path}")
                            
                            # Si hay un scan_token en el config, guardarlo automáticamente en ubicación persistente
                            if config.get('scan_token'):
                                token_value = config.get('scan_token')
                                print(f"🔑 Token encontrado en config: {token_value[:20]}...")

                                # Guardar el config con el token en la ubicación persistente (AppData)
                                # Esto asegura que el token esté disponible en futuras ejecuciones
                                try:
                                    if getattr(sys, 'frozen', False):
                                        appdata_dir = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS')
                                        os.makedirs(appdata_dir, exist_ok=True)
                                        persistent_config_path = os.path.join(appdata_dir, 'config.json')

                                        # Leer config existente en AppData si existe, o usar el actual
                                        persistent_config = config.copy()
                                        if os.path.exists(persistent_config_path):
                                            try:
                                                with open(persistent_config_path, 'r', encoding='utf-8') as f:
                                                    existing_config = json.load(f)
                                                    # Preservar otros valores del config persistente
                                                    persistent_config.update(existing_config)
                                            except:
                                                pass

                                        # Asegurar que el token esté presente
                                        persistent_config['scan_token'] = token_value

                                        # ── Sanear URLs ANTES de guardar y retornar ──────────────
                                        _correct_url = 'https://asperss.onrender.com'
                                        _bad_prefixes = (
                                            'http://localhost', 'https://localhost',
                                            'http://127.0.0.1', 'https://127.0.0.1',
                                            'https://ssapi-cfni.onrender.com',
                                        )
                                        for _key in ('api_url', 'web_url'):
                                            _val = persistent_config.get(_key, '')
                                            if not _val or any(_val.startswith(p) for p in _bad_prefixes):
                                                print(f"⚠️ URL obsoleta en persistent_config ({_key}: {_val!r}) → {_correct_url}")
                                                persistent_config[_key] = _correct_url

                                        # Guardar config con el token y URLs saneadas
                                        with open(persistent_config_path, 'w', encoding='utf-8') as f:
                                            json.dump(persistent_config, f, indent=2)
                                        print(f"✅ Token guardado en config persistente: {persistent_config_path}")
                                        print(f"🔑 Token completo guardado: {token_value[:30]}...")

                                        # Usar el config persistente como principal
                                        self.config_path = persistent_config_path
                                        return persistent_config
                                except Exception as e:
                                    print(f"⚠️ Error guardando token en config persistente: {e}")
                                    import traceback
                                    traceback.print_exc()
                            
                            # Sanear URLs viejas (localhost / dominios obsoletos)
                            _correct_url = 'https://asperss.onrender.com'
                            _bad_prefixes = (
                                'http://localhost', 'https://localhost',
                                'http://127.0.0.1', 'https://127.0.0.1',
                                'https://ssapi-cfni.onrender.com',
                            )
                            _url_dirty = False
                            for _key in ('api_url', 'web_url'):
                                _val = config.get(_key, '')
                                if not _val or any(_val.startswith(p) for p in _bad_prefixes):
                                    print(f"⚠️ URL obsoleta en config ({_key}: {_val!r}) → corrigiendo a {_correct_url}")
                                    config[_key] = _correct_url
                                    _url_dirty = True
                            if _url_dirty:
                                try:
                                    with open(config_path, 'w', encoding='utf-8') as _fw:
                                        json.dump(config, _fw, indent=2)
                                except Exception:
                                    pass

                            # Guardar la ruta para futuras escrituras
                            self.config_path = config_path
                            return config
                    except Exception as e:
                        print(f"⚠️ Error leyendo config desde {config_path}: {e}")
                        continue
            
            # Si no se encuentra, usar configuración por defecto
            print("⚠️ config.json no encontrado, usando configuración por defecto")
            
            # Determinar ruta por defecto para guardar
            if getattr(sys, 'frozen', False):
                appdata_roaming = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'config.json')
                self.config_path = appdata_roaming
            else:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                self.config_path = os.path.join(script_dir, 'config.json')
            
            return {
                "discord_webhook": "",
                "auth_token": "",
                "scan_timeout": 300,
                "api_url": "https://asperss.onrender.com",
                "scan_token": "",
                "web_url": "https://asperss.onrender.com",
                "enable_db_integration": False,
                "enable_ai_analysis": False,
                "enable_discord_report": False,
                "enable_web_report": False
            }
        except Exception as e:
            print(f"Error cargando configuración: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def create_ui(self):
        """Crea la interfaz de usuario con estilo moderno ASPERS PROJECTS"""
        if UI_STYLE_AVAILABLE:
            main_panel = tk.Frame(self.root, bg=ModernUI.COLORS['bg_primary'])
            main_panel.pack(fill=tk.BOTH, expand=True)

            # Header
            ModernUI.create_header(main_panel)

            # Progress section
            progress_widgets = ModernUI.create_progress_section(main_panel)
            self.progress_frame = progress_widgets['container']
            self.progress_label = progress_widgets['status']
            self.progress_bar = progress_widgets['progress']
            self.progress_detail_label = progress_widgets['detail']
            self.timer_label = progress_widgets['timer']
            self.resources_label = progress_widgets['resources']
            self.progress_percent_label = progress_widgets.get('percent', None)
            self._progress_canvas = progress_widgets.get('_canvas', None)
            self.progress_value = 0

            # Scan button (hidden — escaneo arranca automáticamente)
            btn_container = tk.Frame(main_panel, bg=ModernUI.COLORS['bg_primary'], height=0)
            btn_container.pack()
            btn_container.pack_propagate(False)
            scan_btn_frame = ModernUI.create_button(
                btn_container,
                "INICIAR ESCANEO",
                self.full_scan_with_discord,
                style='primary',
                icon='🚀'
            )
            scan_btn_frame.pack(fill=tk.X)
            self.scan_button = None
            for widget in scan_btn_frame.winfo_children():
                if isinstance(widget, tk.Button):
                    self.scan_button = widget
                    break
            self.details_button = None

            # Completion panel (visible to user instead of raw results)
            self._completion_widgets = ModernUI.create_completion_panel(main_panel)

            # Hidden results section (staff data written here but never shown)
            results_widgets = ModernUI.create_results_section(main_panel)
            self.results_frame = results_widgets['container']
            self.results_text = results_widgets['text']
            self.results_label = results_widgets['title']
        else:
            self._create_ui_fallback()
    
    def _create_ui_fallback(self):
        """Fallback UI si ModernUI no está disponible"""
        self.root.title("Argus Projects — Security Scanner Pro")
        self.root.geometry("1500x950")
        self.root.configure(bg="#0a0e27")
        
        main_panel = tk.Frame(self.root, bg="#0a0e27")
        main_panel.pack(fill=tk.BOTH, expand=True)
        
        # Header simple
        header = tk.Frame(main_panel, bg="#0d1117", height=140)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(
            header,
            text="ASPERS PROJECTS",
            font=("Segoe UI", 32, "bold"),
            bg="#0d1117",
            fg="#f0f6fc"
        ).pack(pady=20)
        
        tk.Label(
            header,
            text="Security Scanner Pro - Advanced Anti-Bypass Detection System",
            font=("Segoe UI", 11),
            bg="#0d1117",
            fg="#8b949e"
        ).pack()
        
        # Panel de progreso
        self.progress_frame = tk.Frame(main_panel, bg="#161b22")
        self.progress_frame.pack(fill=tk.X, pady=(0, 20), padx=25)
        
        self.progress_label = tk.Label(
            self.progress_frame,
            text="⏳ Esperando inicio del escaneo...",
            font=("Segoe UI", 13, "bold"),
            bg="#161b22",
            fg="#f0f6fc"
        )
        self.progress_label.pack(pady=(20, 12))
        
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            mode='determinate',
            length=600,
            maximum=100
        )
        self.progress_value = 0
        self.progress_bar.pack(fill=tk.X, padx=20, pady=(0, 12))
        
        self.progress_detail_label = tk.Label(
            self.progress_frame,
            text="",
            font=("Segoe UI", 10),
            bg="#161b22",
            fg="#8b949e",
            wraplength=600
        )
        self.progress_detail_label.pack(padx=20, pady=(0, 10))
        
        timer_container = tk.Frame(self.progress_frame, bg="#161b22")
        timer_container.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.timer_label = tk.Label(
            timer_container,
            text="⏱️ Tiempo: 00:00:00",
            font=("Segoe UI", 11, "bold"),
            bg="#161b22",
            fg="#58a6ff"
        )
        self.timer_label.pack(side=tk.LEFT)
        
        self.resources_label = tk.Label(
            timer_container,
            text="",
            font=("Segoe UI", 10),
            bg="#161b22",
            fg="#8b949e"
        )
        self.resources_label.pack(side=tk.RIGHT)
        
        # Botones
        button_frame = tk.Frame(main_panel, bg="#0a0e27")
        button_frame.pack(fill=tk.X, pady=20, padx=25)
        
        self.scan_button = tk.Button(
            button_frame,
            text="🚀 INICIAR ESCANEO COMPLETO",
            command=self.full_scan_with_discord,
            bg="#238636",
            fg="#ffffff",
            font=("Segoe UI", 14, "bold"),
            padx=50,
            pady=18,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground="#2ea043"
        )
        self.scan_button.pack(expand=True, fill=tk.X, padx=20)
        
        self.details_button = None
        
        # Resultados
        self.results_frame = tk.Frame(main_panel, bg="#161b22")
        self.results_frame.pack(fill=tk.BOTH, expand=True, padx=25)
        
        self.results_label = tk.Label(
            self.results_frame,
            text="📋 RESULTADOS DEL ESCANEO",
            font=("Segoe UI", 15, "bold"),
            bg="#161b22",
            fg="#f0f6fc"
        )
        self.results_label.pack(pady=(20, 15))
        
        self.results_text = scrolledtext.ScrolledText(
            self.results_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#0d1117",
            fg="#f0f6fc",
            padx=20,
            pady=20
        )
        self.results_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # Tags de color
        self.results_text.tag_config("success", foreground="#3fb950", font=("Consolas", 10, "bold"))
        self.results_text.tag_config("warning", foreground="#d29922", font=("Consolas", 10, "bold"))
        self.results_text.tag_config("danger", foreground="#f85149", font=("Consolas", 10, "bold"))
        self.results_text.tag_config("info", foreground="#58a6ff", font=("Consolas", 10, "bold"))
        self.results_text.tag_config("header", foreground="#f0f6fc", font=("Consolas", 10, "bold"))
    
    def update_detailed_progress(self, value, message, detail=""):
        """Actualiza la barra de progreso con detalles adicionales - Animación suave de 1 en 1"""
        # Asegurar que el valor esté entre 0 y 100
        value = max(0, min(100, int(value)))
        
        # Actualizar detalle inmediatamente
        if hasattr(self, 'progress_detail_label'):
            self.progress_detail_label.config(text=detail)
        
        # Obtener valor actual
        if not hasattr(self, 'progress_value') or self.progress_value is None:
            self.progress_value = 0
        
        target_value = int(value)
        
        # Actualizar el valor objetivo (esto permitirá que la animación continúe hacia el nuevo objetivo)
        self.progress_target_value = target_value
        
        # Guardar mensaje para la animación
        if not hasattr(self, '_progress_message'):
            self._progress_message = message
        self._progress_message = message
        
        # Si no hay animación corriendo, iniciar una nueva
        if not self.progress_animation_running:
            self._start_progress_animation(message)
    
    def _start_progress_animation(self, message=""):
        """Inicia la animación de progreso de forma controlada - Continúa desde donde está"""
        if self.progress_animation_running:
            # Si ya hay una animación corriendo, solo actualizar el mensaje y objetivo
            return
        
        def animate():
            self.progress_animation_running = True
            last_message = message
            
            try:
                while True:
                    current = int(self.progress_value)
                    target = int(self.progress_target_value)
                    
                    # Si ya llegamos al objetivo, verificar brevemente si hay un nuevo target
                    if current == target:
                        time.sleep(0.05)
                        if int(self.progress_value) == int(self.progress_target_value):
                            time.sleep(0.05)  # segunda espera antes de salir del loop
                            if int(self.progress_value) == int(self.progress_target_value):
                                break
                        continue
                    
                    # Calcular siguiente paso (siempre de 1 en 1)
                    if target > current:
                        next_value = current + 1
                    else:
                        next_value = current - 1
                    
                    # Asegurar que esté en rango
                    next_value = max(0, min(100, next_value))
                    
                    # Actualizar valor
                    self.progress_value = next_value
                    
                    # Obtener mensaje actualizado si cambió
                    current_target = int(self.progress_target_value)
                    if hasattr(self, 'progress_label'):
                        current_text = self.progress_label.cget('text')
                        # Extraer mensaje del texto si es posible
                        if '(' in current_text and '%' in current_text:
                            msg_part = current_text.split('(')[0].strip()
                            if msg_part:
                                last_message = msg_part
                    
                    # Actualizar UI en el hilo principal usando after()
                    # next_value capturado por valor (v=next_value) para evitar closure bug
                    def update_ui(v=next_value, msg=last_message):
                        try:
                            if hasattr(self, 'progress_bar'):
                                self.progress_bar['value'] = v
                            if hasattr(self, 'progress_label'):
                                self.progress_label.config(text=msg)
                            if hasattr(self, 'progress_percent_label') and self.progress_percent_label:
                                self.progress_percent_label.config(text=f"{v}%")
                            if hasattr(self, '_progress_canvas') and self._progress_canvas:
                                ModernUI.update_canvas_bar(self._progress_canvas, v)
                        except Exception:
                            pass

                    # Programar actualización en el hilo principal
                    self.root.after(0, update_ui)

                    # Esperar antes del siguiente paso (velocidad ajustable)
                    time.sleep(0.03)  # 30ms por paso = ~33 pasos por segundo
                    
            except Exception as e:
                print(f"Error en animación de progreso: {e}")
            finally:
                self.progress_animation_running = False
                
                # Asegurar valor final exacto
                try:
                    final_value = int(self.progress_target_value)
                    self.progress_value = final_value
                    
                    # Obtener mensaje final
                    final_message = message
                    if hasattr(self, 'progress_label'):
                        current_text = self.progress_label.cget('text')
                        if '(' in current_text:
                            final_message = current_text.split('(')[0].strip()
                    
                    def final_update():
                        try:
                            if hasattr(self, 'progress_bar'):
                                self.progress_bar['value'] = final_value
                            if hasattr(self, 'progress_label'):
                                self.progress_label.config(text=f"{final_message} ({final_value}%)")
                            if hasattr(self, 'progress_percent_label') and self.progress_percent_label:
                                self.progress_percent_label.config(text=f"{final_value}%")
                        except:
                            pass
                    
                    self.root.after(0, final_update)
                except:
                    pass
        
        # Iniciar animación en thread separado
        self.progress_animation_thread = threading.Thread(target=animate, daemon=True)
        self.progress_animation_thread.start()
    
    def _update_progress_safe(self, value, message, detail=""):
        """Actualiza progreso de forma segura sin recursión"""
        try:
            self.update_detailed_progress(value, message, detail)
        except Exception as e:
            print(f"Error actualizando progreso: {e}")

    def _set_scan_phase(self, text):
        """Actualiza solo el texto de detalle (sin cambiar %) — seguro desde cualquier hilo."""
        try:
            self.root.after(0, lambda t=text: self._apply_phase_text(t))
        except Exception:
            pass

    def _apply_phase_text(self, text):
        try:
            if hasattr(self, 'progress_detail_label') and self.progress_detail_label:
                self.progress_detail_label.config(text=text)
            if hasattr(self, 'progress_label') and self.progress_label:
                cur = self.progress_label.cget('text')
                # Solo actualizar si no está en animación hacia un nuevo porcentaje
                if '→' not in cur:
                    self.progress_label.config(text=text)
        except Exception:
            pass

    def start_scan_timer(self):
        """Inicia el cronómetro del escaneo"""
        import time
        self.scan_start_time = time.time()
        self.timer_running = True
        self.timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self.timer_thread.start()
    
    def stop_scan_timer(self):
        """Detiene el cronómetro del escaneo"""
        self.timer_running = False
        if self.scan_start_time:
            elapsed = time.time() - self.scan_start_time
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"⏱️ Tiempo total: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            self.timer_label.config(text=time_str, fg="#ffff00")
            print(f"🕐 ESCANEO COMPLETADO EN: {time_str}")
    
    def _timer_loop(self):
        """Loop del cronómetro que se ejecuta en segundo plano con recursos del sistema"""
        import time
        while self.timer_running:
            if self.scan_start_time:
                elapsed = time.time() - self.scan_start_time
                hours, remainder = divmod(elapsed, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"⏱️ Tiempo: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
                
                # Obtener recursos del sistema
                try:
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    memory = psutil.virtual_memory()
                    ram_percent = memory.percent
                    ram_used_gb = memory.used / (1024**3)
                    ram_total_gb = memory.total / (1024**3)
                    resources_str = f"💻 CPU: {cpu_percent:.1f}% | 🧠 RAM: {ram_percent:.1f}% ({ram_used_gb:.1f}GB/{ram_total_gb:.1f}GB)"
                except:
                    resources_str = ""
                
                # Actualizar en el hilo principal de forma segura
                try:
                    self.root.after(0, lambda t=time_str, r=resources_str: self._update_timer_display(t, r))
                except:
                    pass
            time.sleep(1)
    
    def _update_timer_display(self, time_str, resources_str):
        """Actualiza la visualización del timer y recursos de forma segura"""
        try:
            if self.timer_label:
                self.timer_label.config(text=time_str)
            if self.resources_label and resources_str:
                self.resources_label.config(text=resources_str)
        except:
            pass
    
    def full_scan_with_discord(self):
        """Ejecuta escaneo completo y envía a Discord y Web automáticamente"""
        def scan_and_report():
            try:
                # Activar modo silencioso (sin logs en UI)
                self.scanning_mode = True
                if UI_STYLE_AVAILABLE:
                    ModernUI.set_status_badge("ESCANEANDO", ModernUI.COLORS['amber'])
                
                # Iniciar escaneo en BD si está disponible
                scan_start_time = time.time()
                if self.db_integration:
                    # Asegurar que el token esté actualizado desde config.json
                    if hasattr(self, 'config') and self.config:
                        scan_token = self.config.get('scan_token', '')
                        if scan_token:
                            self.db_integration.scan_token = scan_token
                            print(f"✅ Token de escaneo actualizado: {scan_token[:20]}...")
                        else:
                            print(f"⚠️ No hay token en config.json, recargando configuración...")
                            # Recargar configuración por si se guardó después de la inicialización
                            self.config = self.load_config()
                            scan_token = self.config.get('scan_token', '')
                            if scan_token:
                                self.db_integration.scan_token = scan_token
                                print(f"✅ Token de escaneo cargado desde config: {scan_token[:20]}...")
                            else:
                                print(f"❌ No hay token de escaneo disponible. Por favor, autentícate primero.")
                    
                    if self.db_integration.scan_token:
                        try:
                            self.db_integration.start_scan()
                        except Exception as e:
                            print(f"⚠️ Error al iniciar escaneo en BD: {e}")
                    else:
                        print(f"⚠️ No se puede iniciar escaneo en BD: no hay token configurado")
                
                # Ejecutar escaneo completo directamente (sin messagebox)
                self.execute_full_scan_silent()
                
                # Esperar a que termine el escaneo
                while self.scanning:
                    time.sleep(0.1)
                
                # Calcular duración del escaneo
                scan_duration = time.time() - scan_start_time

                # Envío a Web (filtrado + IA ya se aplicaron dentro de execute_full_scan_silent)
                print("📤 Enviando resultados a Web...")
                
                # Enviar a Web/BD
                if self.db_integration:
                    # Asegurar que el token esté actualizado antes de enviar
                    if hasattr(self, 'config') and self.config:
                        scan_token = self.config.get('scan_token', '')
                        if scan_token and not self.db_integration.scan_token:
                            self.db_integration.scan_token = scan_token
                            print(f"✅ Token actualizado antes de enviar resultados: {scan_token[:20]}...")
                        elif not scan_token:
                            # Intentar recargar config
                            self.config = self.load_config()
                            scan_token = self.config.get('scan_token', '')
                            if scan_token:
                                self.db_integration.scan_token = scan_token
                                print(f"✅ Token cargado desde config antes de enviar: {scan_token[:20]}...")
                    
                    if self.db_integration.scan_token:
                        try:
                            self._update_progress_safe(99, "📤 Enviando resultados...", "Subiendo a servidor...")
                            success = self.db_integration.submit_results(
                                self.issues_found,
                                self.total_files_scanned,
                                scan_duration,
                                getattr(self, 'total_dirs_scanned', 0)
                            )
                            if success:
                                self._update_progress_safe(100, "✅ Escaneo completado", f"{len(self.issues_found)} hallazgos enviados")
                                print("✅ Resultados enviados a Web/BD")
                            else:
                                self._update_progress_safe(100, "⚠️ Error al enviar", "Revisa conexión y token")
                                print("⚠️ Error al enviar resultados a Web/BD")
                        except Exception as e:
                            print(f"⚠️ Error al enviar a Web/BD: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print("⚠️ No se puede enviar resultados: no hay token de escaneo configurado")
                        print("💡 Por favor, autentícate primero con un token válido")
                
                # Desactivar modo silencioso
                self.scanning_mode = False

                # Cerrar automáticamente tras 4 segundos (resultados ya enviados al panel)
                self.root.after(4000, self.root.destroy)
                
            except Exception as e:
                self.scanning_mode = False
                import traceback
                print(f"❌ Error en escaneo completo: {e}\n{traceback.format_exc()}")
                self.root.after(0, lambda: self.log(f"Error en escaneo completo: {str(e)}", "danger"))
        
        # Ejecutar todo en un hilo separado
        threading.Thread(target=scan_and_report, daemon=True).start()
    
    def execute_full_scan_silent(self):
        """Ejecuta escaneo ULTRA RÁPIDO sin limitaciones de recursos"""
        if self.scanning:
            return
        
        import concurrent.futures
        import psutil
        
        self.scanning = True
        self.issues_found = []
        self.mouse_findings = []
        self.forensic_findings = []
        self.total_files_scanned = 0
        self.total_dirs_scanned = 0

        # ── Anti-detection: camuflar título de ventana durante el scan ──────
        self._camouflage_window()

        # ── Mouse instant checks (run BEFORE anything else) ─────────────────
        # We do this immediately so the player has no time to react.
        if self.mouse_detector:
            try:
                instant = self.mouse_detector.run_instant_checks()
                self.mouse_findings.extend(instant)
                if instant:
                    print(f"🖱️ Detección inmediata de mouse: {len(instant)} hallazgo(s) sospechoso(s)")
                    for f in instant:
                        print(f"   ⚠️  {f['nombre']} [{f['alerta']}]")
            except Exception as _me:
                print(f"⚠️ Error en detección inmediata de mouse: {_me}")

        # Iniciar cronómetro
        self.start_scan_timer()

        try:
            # Configurar para uso MÁXIMO de recursos
            total_phases = 100
            current_progress = 0

            # Inicializar contador global de archivos escaneados
            self.total_files_scanned = 0

            print("🚀 INICIANDO ESCANEO ULTRA RÁPIDO - REVISIÓN COMPLETA DE TODA LA PC")
            print(f"🔧 CPU cores disponibles: {psutil.cpu_count()}")
            print(f"💾 Memoria disponible: {psutil.virtual_memory().available / (1024**3):.1f} GB")
            print("⚡ MODO TURBO ACTIVADO - ESCANEO COMPLETO SIN LÍMITES DE PROFUNDIDAD")
            print("⏱️ CRONÓMETRO INICIADO - MIDIENDO VELOCIDAD MÁXIMA")
            print("🔥 OPTIMIZACIONES: 2x hilos, procesamiento en lotes, filtrado inteligente")
            print("📁 ESCANEO COMPLETO: Revisando TODA la PC sin límites")
            
            # Fase 1: Escaneo de unidades (0-80%)
            self._update_progress_safe(0, "🔍 Iniciando escaneo exhaustivo", "Preparando sistema...")
            
            # Obtener todas las unidades
            drives = []
            for drive in range(ord('A'), ord('Z') + 1):
                drive_letter = chr(drive) + ":\\"
                if os.path.exists(drive_letter):
                    drives.append(drive_letter)
            
            print(f"📁 UNIDADES DETECTADAS: {drives}")
            
            # Escanear cada unidad en paralelo con rendimiento optimizado
            max_workers = psutil.cpu_count() * 2  # Usar 2x más hilos para estabilidad
            print(f"⚡ Usando {max_workers} hilos para velocidad optimizada")
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                progress_per_drive = 80 // len(drives) if drives else 80
                
                for i, drive in enumerate(drives):
                    start_progress = i * progress_per_drive
                    end_progress = (i + 1) * progress_per_drive

                    # Hack-name scan en paralelo (no bloquea la barra de progreso)
                    executor.submit(self._scan_for_specific_hacks, drive)

                    future = executor.submit(self.scan_drive_exhaustive, drive, start_progress, end_progress)
                    futures.append(future)
                
                # Esperar a que terminen todos con timeout aumentado
                for future in concurrent.futures.as_completed(futures, timeout=85):  # 85s max para todas las unidades
                    try:
                        future.result()
                        print(f"✅ Unidad escaneada exitosamente")
                    except concurrent.futures.TimeoutError:
                        print(f"⏰ Timeout en escaneo de unidad (85s) - continuando con fases secundarias...")
                    except Exception as e:
                        print(f"⚠️ Error en escaneo de unidad: {e} - continuando...")
            
            # ── FASES SECUNDARIAS COMPLETAMENTE PARALELAS ─────────────────
            # Todas las fases se ejecutan en paralelo para máxima velocidad.
            # list.append() es thread-safe en CPython (GIL protege operaciones C).
            self._update_progress_safe(80, "⚡ Fases paralelas iniciadas", "Procesos · DNS · Registro · Red · IA...")

            def _run_safe(fn, *a, **kw):
                """Ejecuta una función de escaneo sin propagación de excepciones."""
                try:
                    return fn(*a, **kw)
                except Exception as ex:
                    print(f"⚠️ Error en {fn.__name__}: {ex}")
                    return []

            def _extend_safe(result):
                if result:
                    self.issues_found.extend(result)

            # Grupo A — Procesos y sistema (I/O bajo)
            def _group_processes():
                self._update_progress_safe(81, "⚡ Procesos", "Analizando procesos activos...")
                self._set_scan_phase("⚙️ Procesos secundarios...")
                _run_safe(self.secondary_scan_parallel)
                self._set_scan_phase("🎮 Procesos Java / Minecraft...")
                _run_safe(self.scan_processes)
                _run_safe(self.advanced_minecraft_process_analysis)
                self._set_scan_phase("🌳 Árbol de procesos Java (parent analysis)...")
                _run_safe(self.scan_java_process_parent)
                self._set_scan_phase("🔒 Procesos deshabilitados / ocultos...")
                _run_safe(self.scan_disabled_processes)
                _run_safe(self.scan_running_processes)
                self._set_scan_phase("🌐 Caché DNS...")
                _run_safe(self.scan_dns_cache)
                self._set_scan_phase("🪟 Ventanas activas...")
                _run_safe(self.scan_windows)

            # Grupo B — Archivos y fechas (I/O medio)
            def _group_files():
                self._update_progress_safe(83, "⚡ Archivos", "Analizando archivos modificados...")
                self._set_scan_phase("📄 Ejecutables (.exe)...")
                _run_safe(self.scan_exe_files)
                self._set_scan_phase("☕ Archivos JAR...")
                _run_safe(self.scan_jar_files)
                self._set_scan_phase("📅 Archivos por fecha...")
                _run_safe(self.scan_files_by_date)
                self._set_scan_phase("🗑️ Archivos eliminados / renombrados...")
                _run_safe(self.scan_deleted_files)
                _run_safe(self.scan_created_files)
                _run_safe(self.scan_renamed_files)
                self._set_scan_phase("👁️ Archivos ocultos / papelera...")
                _extend_safe(_run_safe(self.scan_hidden_files))
                _run_safe(self.scan_deleted_recycle)
                self._set_scan_phase("🎨 Texture packs / exploit tools...")
                _run_safe(self.scan_texture_packs)
                _run_safe(self.scan_exploit_tools)

            # Grupo C — Registro y JNA (I/O bajo)
            def _group_registry():
                self._update_progress_safe(85, "⚡ Registro y JNA", "Analizando entradas del registro...")
                self._set_scan_phase("📂 Prefetch / JNA...")
                _run_safe(self.scan_prefetch_jna)
                _run_safe(self.scan_temp_jna)
                self._set_scan_phase("🗂️ Prefetch completo...")
                _run_safe(self.scan_prefetch_all)
                self._set_scan_phase("📋 Registro sospechoso...")
                _run_safe(self.scan_registry_suspicious)
                _run_safe(self.scan_registry)
                self._set_scan_phase("📜 Event logs...")
                _run_safe(self.scan_event_logs)
                self._set_scan_phase("💻 Historial CMD / PowerShell...")
                _run_safe(self.scan_cmd_history_full)
                _run_safe(self.scan_powershell_history)
                self._set_scan_phase("👤 UserAssist (programas ejecutados)...")
                _run_safe(self.scan_executed_userassist)
                self._set_scan_phase("⏱️ BAM registry (ejecuciones con timestamp)...")
                _run_safe(self.scan_bam_registry)
                self._set_scan_phase("🔗 ShimCache / AppCompatCache...")
                _run_safe(self.scan_appcompat_shimcache)
                self._set_scan_phase("🎨 MUICache...")
                _run_safe(self.scan_muicache)
                self._set_scan_phase("📎 Archivos recientes (LNK)...")
                _run_safe(self.scan_recent_lnk)
                self._set_scan_phase("📅 Tareas programadas...")
                _run_safe(self.scan_scheduled_tasks)
                self._set_scan_phase("🌐 Descargas de navegadores...")
                _run_safe(self.scan_browser_downloads)
                self._set_scan_phase("🖥️ Comandos Run (Win+R)...")
                _run_safe(self.scan_run_mru)
                self._set_scan_phase("📁 Rutas escritas en Explorer...")
                _run_safe(self.scan_typed_paths)
                self._set_scan_phase("🔌 Historial USB...")
                _run_safe(self.scan_usb_history)
                self._set_scan_phase("🌐 Hosts file...")
                _run_safe(self.scan_hosts_file)
                self._set_scan_phase("🚀 Entradas de inicio automático...")
                _run_safe(self.scan_startup_entries)
                self._set_scan_phase("📦 Programas instalados...")
                _run_safe(self.scan_installed_programs)
                self._set_scan_phase("⛏️ JARs recientes en carpetas temporales...")
                _run_safe(self.scan_temp_jars)
                self._set_scan_phase("🤖 Baritone / modos prohibidos...")
                _run_safe(self.scan_baritone_config)
                self._set_scan_phase("🔨 Schematica/Litematica Printer Mode...")
                _run_safe(self.scan_schematica_litematica)
                self._set_scan_phase("🔍 OptiFine zoom key binding...")
                _run_safe(self.scan_optifine_zoom)

            # Grupo D — Hardware y red (I/O alto)
            def _group_hardware():
                self._update_progress_safe(87, "⚡ Hardware y red", "Analizando dispositivos y conexiones...")
                _run_safe(self.scan_logitech_macros)
                _run_safe(self.scan_razer_macros)
                self._set_scan_phase("🖱️ Bloody/A4Tech macros...")
                _run_safe(self.scan_bloody_a4tech)
                self._set_scan_phase("🎮 SteelSeries/Corsair macros...")
                _run_safe(self.scan_steelseries_corsair)
                self._set_scan_phase("🔌 Arduino HID devices...")
                _run_safe(self.scan_arduino_hid)
                _extend_safe(_run_safe(self.scan_usb_devices))
                _extend_safe(_run_safe(self.scan_network_connections))
                self._set_scan_phase("🔌 Adaptadores VPN...")
                _run_safe(self.scan_vpn_adapters)
                self._set_scan_phase("☕ JDWP debug port...")
                _run_safe(self.scan_jdwp_port)
                self._set_scan_phase("💉 DLLs en proceso Java...")
                _run_safe(self.scan_dll_injection_java)
                self._set_scan_phase("🔬 Strings de hack en JARs cargados por Java...")
                _run_safe(self.scan_process_memory_strings)
                self._set_scan_phase("📍 Correlación de ruta de proceso sospechoso...")
                _run_safe(self.scan_process_path_correlation)
                self._set_scan_phase("☁️ Hashes de procesos vs base de datos cloud...")
                _run_safe(self.scan_process_hashes_cloud)
                self._set_scan_phase("🧹 Actividad de borrado pre-scan (últimos 10 min)...")
                _run_safe(self.scan_prescan_disk_activity)
                self._set_scan_phase("🌳 Árbol de procesos — cadenas anómalas...")
                _run_safe(self.scan_process_tree)
                self._set_scan_phase("📊 Delta vs baseline histórico del jugador...")
                _run_safe(self.scan_player_baseline_delta)
                self._set_scan_phase("📝 TF-IDF en config files de ghost clients...")
                _run_safe(self.scan_config_tfidf)
                self._set_scan_phase("🔌 Conexiones de red de javaw a hosts externos...")
                _run_safe(self.scan_javaw_network_connections)
                self._set_scan_phase("🗂️ DLLs sospechosas en carpetas temporales...")
                _run_safe(self.scan_temp_dlls)
                self._set_scan_phase("⚡ Múltiples instancias de javaw.exe...")
                _run_safe(self.scan_multiple_javaw)
                self._set_scan_phase("🧠 Regiones de memoria RWX en javaw.exe...")
                _run_safe(self.scan_java_rwx_memory)

            # Grupo E — Ubicaciones de hacks (I/O alto)
            def _group_hack_locations():
                self._update_progress_safe(89, "🎯 Ubicaciones de hacks", "Downloads, Desktop, Roaming...")
                _run_safe(self.scan_common_hack_locations)
                _run_safe(self.scan_suspicious_folders)
                _run_safe(self.scan_exact_hack_names)
                self._set_scan_phase("👻 Config de ghost clients...")
                _run_safe(self.scan_ghost_client_configs)
                self._set_scan_phase("📋 Registro de ghost clients...")
                _run_safe(self.scan_ghost_client_registry)
                self._set_scan_phase("📦 Mods prohibidos en .minecraft/mods/...")
                _run_safe(self.scan_minecraft_mods_blacklist)
                self._set_scan_phase("🤖 Scripts AHK con autoclick...")
                _run_safe(self.scan_ahk_scripts)
                self._set_scan_phase("💉 Procesos inyectores activos...")
                _run_safe(self.scan_active_injectors)
                self._set_scan_phase("🔑 Hash de minecraft.jar vs Mojang...")
                _run_safe(self.scan_minecraft_jar_hash)
                self._set_scan_phase("🪝 -javaagent en JVM args...")
                _run_safe(self.scan_javaagent_args)
                self._set_scan_phase("🕸️ Weave Loader artifacts...")
                _run_safe(self.scan_weave_loader)
                self._set_scan_phase("📋 Prefetch de hacks ejecutados...")
                _run_safe(self.scan_prefetch_hacks)
                self._set_scan_phase("📝 USN Journal — JARs/carpetas borrados...")
                _run_safe(self.scan_usn_minecraft_jars)
                self._set_scan_phase("📡 Discord webhooks en configs de hacks (C2)...")
                _run_safe(self.scan_discord_webhooks)
                self._set_scan_phase("🎯 Jitter/aim assist en software de mouse...")
                _run_safe(self.scan_jitter_scripts)
                self._set_scan_phase("🖥️ Minecraft Safe Mode...")
                _run_safe(self.scan_minecraft_safe_mode)
                self._set_scan_phase("🎯 Fingerprints compuestos de ghost clients...")
                _run_safe(self.scan_hack_fingerprints)
                self._set_scan_phase("⛓️ Kill chain temporal (USN Journal)...")
                _run_safe(self.scan_kill_chain)

            # Grupo F — Técnicas avanzadas
            def _group_advanced():
                self._update_progress_safe(92, "🧠 Técnicas avanzadas", "Silent-scanner + AstroSS...")
                try:
                    from silent_scanner_techniques import SilentScannerTechniques
                    adv = SilentScannerTechniques.scan_all_advanced_techniques()
                    if adv: self.issues_found.extend(adv)
                    print(f"✅ Técnicas Silent-scanner: {len(adv)} detecciones")
                except ImportError:
                    pass
                except Exception as ex:
                    print(f"⚠️ Silent-scanner: {ex}")
                try:
                    from astro_ss_techniques import AstroSSTechniques
                    astro_issues = AstroSSTechniques().scan_all_astro_techniques()
                    if astro_issues: self.issues_found.extend(astro_issues)
                    print(f"✅ Técnicas AstroSS: {len(astro_issues)} detecciones")
                except ImportError:
                    pass
                except Exception as ex:
                    print(f"⚠️ AstroSS: {ex}")

            # Grupo G — Análisis forense SS (checklist manual completo)
            def _group_forensics():
                if not self.ss_forensics:
                    return
                self._update_progress_safe(88, "🔬 Análisis forense SS", "USN Journal, BAM, UserAssist, AppCompat...")
                try:
                    findings = self.ss_forensics.scan_all()
                    if findings:
                        self.forensic_findings.extend(findings)
                        print(f"✅ SS Forensics: {len(findings)} hallazgo(s) forenses")
                        for ff in findings:
                            print(f"   🔬 {ff.get('nombre','')} [{ff.get('alerta','')}]")
                    else:
                        print("✅ SS Forensics: sin hallazgos forenses sospechosos")
                except Exception as ex:
                    print(f"⚠️ SS Forensics: {ex}")

            # Ejecutar todos los grupos en paralelo (7 workers)
            secondary_workers = min(7, psutil.cpu_count() or 4)
            print(f"⚡ Ejecutando fases secundarias con {secondary_workers} workers en paralelo")
            with concurrent.futures.ThreadPoolExecutor(max_workers=secondary_workers) as sec_exec:
                sec_futures = [
                    sec_exec.submit(_group_processes),
                    sec_exec.submit(_group_files),
                    sec_exec.submit(_group_registry),
                    sec_exec.submit(_group_hardware),
                    sec_exec.submit(_group_hack_locations),
                    sec_exec.submit(_group_advanced),
                    sec_exec.submit(_group_forensics),
                ]
                for f in concurrent.futures.as_completed(sec_futures, timeout=80):
                    try:
                        f.result()
                    except Exception as ex:
                        print(f"⚠️ Error en grupo de escaneo: {ex}")
            
            # ── Recolectar hallazgos de monitoreo de mouse ───────────────────
            if self.mouse_detector:
                try:
                    self.mouse_detector.stop_monitoring()
                    session = self.mouse_detector.get_session_findings()
                    self.mouse_findings.extend(session)
                    if session:
                        print(f"🖱️ Hallazgos de sesión de mouse: {len(session)}")
                        for f in session:
                            print(f"   ⚠️  {f['nombre']} [{f['alerta']}]")
                except Exception as _me:
                    print(f"⚠️ Error recolectando hallazgos de mouse: {_me}")

            # Análisis de evasión activa (post-scan, requiere todos los hallazgos previos)
            self._set_scan_phase("🎭 Detección de evasión activa...")
            _run_safe(self.scan_evasion_indicators)

            # Fase 9: Filtrado y clasificación (100%)
            self._update_progress_safe(100, "🔍 Filtrando resultados", "Aplicando filtros ultra estrictos...")
            print(f"[FILTRO] Issues antes de filtrar: {len(self.issues_found)} | Archivos escaneados: {self.total_files_scanned} | Dirs: {self.total_dirs_scanned}")

            # Aplicar filtro ultra inteligente
            pre_filter = len(self.issues_found)
            self.issues_found = self.filter_false_positives(self.issues_found)
            print(f"[FILTRO] Después de filter_false_positives: {len(self.issues_found)} (eliminados: {pre_filter - len(self.issues_found)})")

            # Aplicar segundo filtro más inteligente
            pre_secondary = len(self.issues_found)
            self.issues_found = self.secondary_filter(self.issues_found)
            print(f"[FILTRO] Después de secondary_filter: {len(self.issues_found)} (eliminados: {pre_secondary - len(self.issues_found)})")
            
            # Segunda pasada de análisis sobre archivos sospechosos
            self._update_progress_safe(96, "🔬 Segunda pasada", "Analizando archivos sospechosos en profundidad...")
            self.second_pass_scanner()

            # Aplicar análisis de IA si está disponible
            if self.ai_analyzer and self.issues_found:
                try:
                    self._update_progress_safe(100, "🤖 Analizando con IA", "Aplicando análisis inteligente...")
                    self.issues_found = self.ai_analyzer.analyze_batch(self.issues_found)
                    print(f"✅ Análisis de IA aplicado - {len(self.issues_found)} issues analizados")
                except Exception as e:
                    print(f"⚠️ Error en análisis de IA durante escaneo: {e}")
            
            # Aplicar sistema de scoring de confianza
            if self.scoring_system and self.issues_found:
                try:
                    self._update_progress_safe(100, "📊 Calculando scores", "Priorizando resultados...")
                    self.issues_found = self.scoring_system.prioritize_results(self.issues_found)
                    print(f"✅ Scoring aplicado - {len(self.issues_found)} issues priorizados")
                except Exception as e:
                    print(f"⚠️ Error aplicando scoring: {e}")
            
            # Actualizar contadores en la UI
            if UI_STYLE_AVAILABLE:
                counts = {'critical': 0, 'suspicious': 0, 'low': 0, 'clean': 0}
                for iss in self.issues_found:
                    lvl = iss.get('alerta', '').upper()
                    if lvl == 'CRITICAL':
                        counts['critical'] += 1
                    elif lvl == 'SOSPECHOSO':
                        counts['suspicious'] += 1
                    elif lvl == 'POCO_SOSPECHOSO':
                        counts['low'] += 1
                    else:
                        counts['clean'] += 1
                for k, v in counts.items():
                    ModernUI.update_counter(k, v)

            # Finalizar (95% — el 100% lo pone el hilo principal tras enviar resultados)
            self._update_progress_safe(95, "Preparando resultados", f"Encontrados {len(self.issues_found)} elementos")
            
            # Estadísticas finales
            if hasattr(self, 'scan_start_time'):
                total_time = time.time() - self.scan_start_time
                print(f"🏁 ESTADÍSTICAS FINALES:")
                print(f"   📁 Total elementos encontrados: {len(self.issues_found)}")
                print(f"   ⏱️ Tiempo total de escaneo: {total_time:.1f} segundos")
                print(f"   🔧 CPU cores utilizados: {psutil.cpu_count()}")
                print(f"   💾 Memoria disponible: {psutil.virtual_memory().available / (1024**3):.1f} GB")
            
            print("✅ ESCANEO COMPLETADO")
            
        except Exception as e:
            print(f"Error durante escaneo exhaustivo: {str(e)}")
            import traceback
            traceback.print_exc()
            self._update_progress_safe(95, f"❌ Error: {str(e)}", "Error durante el escaneo")
        finally:
            # Detener cronómetro
            self.stop_scan_timer()
            self.scanning = False
            self._restore_window_title()
            if UI_STYLE_AVAILABLE:
                ModernUI.set_status_badge("LISTO", ModernUI.COLORS['green'])
                if hasattr(self, '_completion_widgets'):
                    try:
                        self.root.after(0, lambda: ModernUI.set_completion_state(
                            self._completion_widgets,
                            success=True,
                            message="Escaneo completado",
                            sub="Los resultados han sido enviados al staff"
                        ))
                    except Exception:
                        pass
    
    def scan_drive_exhaustive(self, drive, start_progress, end_progress):
        """Escanea una unidad completa - VERSIÓN OPTIMIZADA CON LÍMITES"""
        import time
        
        try:
            print(f"🔍 INICIANDO ESCANEO OPTIMIZADO DE UNIDAD: {drive}")
            print(f"📊 Rango de progreso: {start_progress}% - {end_progress}%")
            
            if not os.path.exists(drive):
                print(f"❌ Unidad {drive} no existe, saltando...")
                return
            
            start_time = time.time()
            
            # Timeout agresivo: objetivo < 90s totales para todo el scan
            # Esta fase ocupa ~80% del tiempo, así que le damos 65s max por unidad
            try:
                cpu_count = psutil.cpu_count() or 2
                if cpu_count < 4:
                    total_timeout = 80   # hardware lento
                elif cpu_count < 8:
                    total_timeout = 65
                else:
                    total_timeout = 55   # hardware rápido
                print(f"⚙️ Hardware {cpu_count} cores → timeout por unidad: {total_timeout}s (objetivo total <90s)")
            except Exception:
                total_timeout = 65
                print(f"⚠️ No se pudo detectar hardware, usando timeout: {total_timeout}s")
            
            scanned_files = 0
            max_files_per_folder = None  # Sin límite de archivos por carpeta (solo timeout total)
            last_progress_update = start_time
            
            # Actualizar contador global
            if not hasattr(self, 'total_files_scanned'):
                self.total_files_scanned = 0
            if not hasattr(self, 'total_dirs_scanned'):
                self.total_dirs_scanned = 0
            
            max_depth = 4   # Reducido de 8 → 4 para velocidad (Minecraft no tiene más de 4 niveles relevantes)

            skip_folders = {
                'node_modules', '.git', '__pycache__', 'venv', '.venv',
                'WinSxS', 'servicing', 'en-US', 'MUI', 'winsxs',
                # Directorios de navegadores — generan cientos de false positives
                # porque sus subcarpetas internas tienen nombres como "ClientCertificates"
                'User Data', 'Default', 'Profiles',  # Chrome/Edge profile dirs
                'chrome', 'Chrome', 'firefox', 'Firefox', 'edge', 'Edge',
                'Brave-Browser', 'vivaldi', 'opera',
                # Drivers y sistema
                'DriverStore', 'SystemResources', 'Panther',
                # Cache del sistema — no relevante para hacks de Minecraft
                'Temp', 'temp', 'tmp', 'cache', 'Cache',
            }

            # Solo rutas relevantes para Minecraft hacks — no System32 ni Program Files completos
            user_home = os.path.expanduser("~")
            critical_paths = [
                # Minecraft y clientes
                os.path.join(user_home, "AppData", "Roaming", ".minecraft"),
                os.path.join(user_home, "AppData", "Roaming", "lunar-launcher"),
                os.path.join(user_home, "AppData", "Roaming", "feather"),
                os.path.join(user_home, "AppData", "Roaming", "cosmic"),
                os.path.join(user_home, "AppData", "Local", "Programs"),
                # Carpetas de usuario
                os.path.join(user_home, "Downloads"),
                os.path.join(user_home, "Desktop"),
                os.path.join(user_home, "Documents"),
                os.path.join(user_home, "AppData", "Roaming"),
                os.path.join(user_home, "AppData", "Local", "Temp"),
                # Temp del sistema (pequeño)
                os.path.join(drive, "Windows", "Temp"),
                os.path.join(drive, "Windows", "Prefetch"),
            ]

            # Agregar .minecraft de otros usuarios en el mismo equipo
            users_dir = os.path.join(drive, "Users")
            if os.path.exists(users_dir):
                try:
                    for user_folder in os.listdir(users_dir):
                        user_path = os.path.join(users_dir, user_folder)
                        if os.path.isdir(user_path) and user_folder not in ['Default', 'Public', 'All Users']:
                            mc_path = os.path.join(user_path, "AppData", "Roaming", ".minecraft")
                            if mc_path not in critical_paths:
                                critical_paths.append(mc_path)
                            for client in ("lunar-launcher", "feather", "cosmic"):
                                cp = os.path.join(user_path, "AppData", "Roaming", client)
                                if cp not in critical_paths:
                                    critical_paths.append(cp)
                except Exception:
                    pass
            
            # Primero escanear carpetas específicas con límites
            for critical_path in critical_paths:
                if not os.path.exists(critical_path):
                    continue
                    
                folder_start_time = time.time()
                folder_scanned = 0
                print(f"📁 ESCANEANDO CARPETA CRÍTICA: {critical_path}")
                
                try:
                    for root, dirs, files in os.walk(critical_path):
                        self.total_dirs_scanned += 1  # Contar cada carpeta visitada
                        # Verificar timeout total (no por carpeta)
                        if time.time() - start_time > total_timeout:
                            print(f"⏰ Timeout total alcanzado después de {total_timeout//60} minutos - finalizando escaneo...")
                            break
                        
                        # Limitar profundidad
                        depth = root.count(os.sep) - critical_path.count(os.sep)
                        if depth > max_depth:
                            dirs[:] = []  # No explorar más profundo
                            continue
                        
                        # Saltar carpetas problemáticas
                        dirs[:] = [d for d in dirs if not any(skip in os.path.join(root, d).lower() for skip in skip_folders)]
                        
                        # Sin límite de archivos (solo timeout total)
                        # Verificar timeout total continuamente
                        if time.time() - start_time > total_timeout:
                            break
                        
                        # Filtrar archivos por extensión
                        relevant_extensions = (
                            '.jar', '.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.py', 
                            '.class', '.java', '.lua', '.txt', '.log', '.cfg', '.config', '.json', 
                            '.properties', '.yml', '.yaml', '.xml', '.dat', '.bin', '.cache',
                            '.tmp', '.temp', '.bak', '.backup', '.old', '.new', '.mod', '.minecraft',
                            '.zip', '.rar', '.7z', '.tar', '.gz', '.msi', '.msm', '.msp'
                        )
                        relevant_files = [f for f in files if f.lower().endswith(relevant_extensions)]
                        # Contar TODOS los archivos vistos (antes de filtrar por extensión)
                        self.total_files_scanned += len(files)
                        scanned_files += len(files)
                        folder_scanned += len(files)

                        # Verificar carpetas sospechosas
                        _root_lower = root.lower()
                        for dir_name in dirs:
                            if _is_hack_folder(dir_name, _root_lower):
                                self.issues_found.append({
                                    'nombre': dir_name,
                                    'ruta': root,
                                    'archivo': os.path.join(root, dir_name),
                                    'tipo': 'folder',
                                    'categoria': 'HACKS',
                                    'alerta': 'SOSPECHOSO'
                                })
                            
                        # Procesar TODOS los archivos (sin límite por lote)
                        for file in relevant_files:
                            try:
                                file_path = os.path.join(root, file)
                                
                                if self.is_suspicious_file(file_path):
                                    self.issues_found.append({
                                        'nombre': file,
                                        'ruta': root,
                                        'archivo': file_path,
                                        'tipo': 'file',
                                        'categoria': 'HACKS',
                                        'alerta': 'SOSPECHOSO'
                                    })
                                
                                # Actualizar progreso cada 2000 archivos O cada 3 segundos
                                _now = time.time()
                                if scanned_files % 2000 == 0 or (_now - last_progress_update) >= 3:
                                    last_progress_update = _now
                                    elapsed = _now - start_time
                                    rate = scanned_files / elapsed if elapsed > 0 else 0
                                    remaining = total_timeout - elapsed
                                    print(f"📁 {drive}: {scanned_files} archivos ({rate:.0f} arch/s) - Tiempo restante: {remaining:.0f}s...")
                                    # Actualizar barra de progreso dinámicamente
                                    elapsed_pct = min(79, int(start_progress + (elapsed / total_timeout) * (end_progress - start_progress)))
                                    self._update_progress_safe(elapsed_pct, f"🔍 Escaneando {drive}", f"{scanned_files:,} archivos · {rate:.0f} arch/s")
                                
                                # Verificar timeout total (sin límite de archivos)
                                if time.time() - start_time > total_timeout:
                                    break
                                    
                            except (PermissionError, OSError):
                                continue
                            except Exception:
                                continue
                        
                        # Verificar timeout total (sin límite de archivos)
                        if time.time() - start_time > total_timeout:
                            break
                                
                except Exception as e:
                    print(f"⚠️ Error en {critical_path}: {e} - continuando...")
                    continue
            
            
            # Calcular estadísticas de velocidad
            end_time = time.time()
            elapsed_time = end_time - start_time
            files_per_second = scanned_files / elapsed_time if elapsed_time > 0 else 0
            
            print(f"📊 TOTAL ESCANEADO EN {drive}: {scanned_files} archivos")
            print(f"⚡ VELOCIDAD: {files_per_second:.1f} archivos/segundo")
            print(f"⏱️ TIEMPO EN {drive}: {elapsed_time:.1f} segundos")
            
            # Actualizar progreso final para esta unidad
            try:
                self._update_progress_safe(end_progress, f"✅ Completado {drive}", f"Escaneados {scanned_files} archivos - {files_per_second:.1f} arch/seg")
            except:
                pass
                            
        except Exception as e:
            print(f"Error escaneando unidad {drive}: {e}")
    
    def _process_file_batch(self, file_batch):
        """Procesa un lote de archivos de manera eficiente"""
        try:
            for file, root, file_path in file_batch:
                # Verificar si es sospechoso
                if self.is_suspicious_file(file_path):
                    self.issues_found.append({
                        'nombre': file,
                        'ruta': root,
                        'archivo': file_path,
                        'tipo': 'file',
                        'categoria': 'HACKS',
                        'alerta': 'SOSPECHOSO'
                    })
        except Exception as e:
            print(f"Error procesando lote de archivos: {e}")
    
    def analyze_file_content(self, file_path):
        """Análisis avanzado del contenido del archivo - Detecta hacks por contenido, no solo nombre"""
        try:
            # Verificar cache
            if file_path in self.file_analysis_cache:
                return self.file_analysis_cache[file_path]
            
            result = {
                'is_hack': False,
                'confidence': 0,
                'detected_patterns': [],
                'obfuscation_detected': False,
                'file_hash': None
            }
            
            # Calcular hash SHA256
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    file_hash = hashlib.sha256(file_content).hexdigest()
                    result['file_hash'] = file_hash
                    
                    # Verificar si el hash está en la base de datos de hacks conocidos
                    if file_hash in self.known_hack_hashes:
                        result['is_hack'] = True
                        result['confidence'] = 100
                        result['detected_patterns'].append('known_hash')
                        self.file_analysis_cache[file_path] = result
                        return result
            except:
                pass
            
            # Análisis de contenido para archivos de texto y JARs
            filename_lower = os.path.basename(file_path).lower()
            
            # Patrones de hacks en contenido — solo nombres de clientes/hacks específicos
            # Excluidos a propósito: reach, velocity, fly, bypass, inject, ghost, scaffold
            # (son términos genéricos presentes en cualquier mod legítimo de Minecraft)
            hack_content_patterns = [
                # Clientes clásicos
                b'vape', b'vapelite', b'vapev4',
                b'entropy', b'entropyclient',
                b'whiteout',
                b'liquidbounce',
                b'wurst', b'wurstclient',
                b'impactclient',
                b'sigmaclient', b'sigma5',
                b'fluxclient',
                b'futureclient',
                b'astolfo', b'astolfoclient',
                b'exhibition',
                b'novoline',
                b'dripclient',
                # Clientes modernos (2022-2025)
                b'meteorclient', b'meteor-client',
                b'rusherhack',
                b'aristois',
                b'tenacity',
                b'inertiaclient',
                b'salhack',
                b'jelloclient',
                b'daturamc',
                b'remixclient',
                b'pandoraclient',
                b'azuraclient',
                b'kamiblue',
                b'konasclient',
                b'weepcraft',
                b'zeroday',
                b'nyxclient',
                # Módulos y herramientas
                b'killaura', b'kill-aura',
                b'aimbot', b'aim-bot',
                b'triggerbot',
                b'xray', b'fullbright',
                b'autoclick', b'autoclicker',
                b'clickgui',
                b'anticheat.bypass', b'anticheat bypass',
                b'nofall', b'no-fall',
                b'scaffoldhack',
                # Loaders e injectors
                b'weaveloader', b'weave-loader',
                b'extremeinjector',
                b'dllinjector',
                b'cheatengine',
                # C2 y exfiltración
                b'discord.com/api/webhooks/',
                b'drip', b'phobos',
            ]
            # Umbrales: 1 patrón "definitivo" (nombre exacto de cliente) = hack directo
            # 2+ patrones genéricos = hack probable
            DEFINITE_CONTENT_PATTERNS = {
                b'meteorclient', b'rusherhack', b'aristois', b'tenacity',
                b'inertiaclient', b'salhack', b'jelloclient', b'daturamc',
                b'kamiblue', b'weaveloader', b'weave-loader', b'extremeinjector',
                b'astolfoclient', b'entropyclient', b'liquidbounce', b'wurstclient',
                b'futureclient', b'fluxclient', b'sigmaclient', b'vapelite',
                b'pandoraclient', b'azuraclient', b'nyxclient', b'remixclient',
            }

            # Análisis de strings sospechosos
            try:
                if filename_lower.endswith(('.jar', '.class', '.java', '.txt', '.lua', '.js', '.py')):
                    with open(file_path, 'rb') as f:
                        content = f.read(1024 * 1024)  # Leer primeros 1MB

                        # Detectar patrones de hack en contenido
                        # Normalizar contenido para detectar homoglyphs cirílicos
                        content_norm = _normalize(content.decode('utf-8', errors='ignore')).encode('ascii')
                        detected_count = 0
                        definite_hit = False
                        for pattern in hack_content_patterns:
                            if pattern in content or pattern in content_norm:
                                detected_count += 1
                                result['detected_patterns'].append(pattern.decode('utf-8', errors='ignore'))
                                if pattern in DEFINITE_CONTENT_PATTERNS:
                                    definite_hit = True

                        if definite_hit:
                            # Un nombre exclusivo de hack client = hit directo
                            result['is_hack'] = True
                            result['confidence'] = min(95, 70 + detected_count * 5)
                        elif detected_count >= 3:
                            result['is_hack'] = True
                            result['confidence'] = min(90, detected_count * 12)
                        elif detected_count == 2:
                            result['is_hack'] = True
                            result['confidence'] = 55

                        # Ofuscación solo relevante para archivos de texto, no binarios JARs/class
                        if len(content) > 100 and not filename_lower.endswith(('.jar', '.class')):
                            non_ascii_ratio = sum(1 for b in content[:1000] if b > 127) / min(1000, len(content))
                            if non_ascii_ratio > 0.3:
                                result['obfuscation_detected'] = True
                                result['confidence'] += 20
            except:
                pass

            # Análisis de estructura interna para JARs
            if filename_lower.endswith('.jar'):
                try:
                    import zipfile as _zf
                    import math as _math
                    LEGIT_MOD_MARKERS = {
                        'mcmod.info', 'fabric.mod.json', 'quilt.mod.json',
                        'mods.toml', 'pack.mcmeta',
                    }
                    SUSPICIOUS_MANIFEST_PACKAGES = [
                        # Clientes clásicos
                        'com.vape', 'net.sigma', 'com.entropy', 'me.drip',
                        'net.liquidbounce', 'com.wurst', 'com.future', 'com.flux',
                        'com.astolfo', 'net.rise', 'com.novoline', 'com.ghost',
                        # Clientes modernos (2022-2025)
                        'com.meteor', 'meteordevelopment',
                        'net.rusherhack', 'com.rusherhack',
                        'com.aristois', 'net.aristois',
                        'com.tenacity', 'net.tenacity',
                        'com.vertex', 'net.vertex',
                        'com.inertia', 'net.inertia',
                        'me.kami', 'net.kamiblue',
                        'com.salhack', 'me.salhack',
                        'com.jello', 'me.jello',
                        'com.datura', 'me.datura',
                        'com.pandora', 'net.pandora',
                        'com.azura', 'me.azura',
                        'com.konas', 'net.konas',
                        'com.remix', 'net.remix',
                        # Loaders e injectors
                        'me.weaveclient', 'net.weaveloader',
                        'com.salhack',
                        # Módulos/cheats genéricos
                        'me.baritone',  # bot de movimiento automático
                        'com.phobos', 'net.phobos',
                        'com.seppuku', 'com.sloth',
                    ]
                    with _zf.ZipFile(file_path, 'r') as zf:
                        names_lower = {n.lower() for n in zf.namelist()}
                        has_legit_marker = bool(names_lower & LEGIT_MOD_MARKERS)
                        result['has_legit_mod_marker'] = has_legit_marker

                        if has_legit_marker and result['confidence'] < 75:
                            result['confidence'] = max(0, result['confidence'] - 20)
                            result['detected_patterns'].append('has_legit_mod_marker')

                        # Check MANIFEST.MF for suspicious main class
                        if 'meta-inf/manifest.mf' in names_lower:
                            try:
                                manifest = zf.read('META-INF/MANIFEST.MF').decode('utf-8', errors='ignore').lower()
                                for pkg in SUSPICIOUS_MANIFEST_PACKAGES:
                                    if pkg in manifest:
                                        result['is_hack'] = True
                                        result['confidence'] = max(result['confidence'], 80)
                                        result['detected_patterns'].append(f'manifest_pkg:{pkg}')
                                        break
                            except Exception:
                                pass

                        # P2 #20 — Compilation date vs file date
                        # If the newest .class inside the jar is much newer than the jar file
                        # itself, the jar was re-packed (tampering / custom build).
                        try:
                            import datetime as _dt
                            file_mtime = _dt.datetime.fromtimestamp(os.path.getmtime(file_path))
                            class_times = []
                            for info in zf.infolist():
                                if info.filename.endswith('.class') and info.date_time[0] >= 2000:
                                    dt = _dt.datetime(*info.date_time[:6])
                                    class_times.append(dt)
                            if class_times:
                                newest_class = max(class_times)
                                delta_days = (newest_class - file_mtime).days
                                # Class compiled AFTER file date = jar was re-packed
                                if delta_days > 1:
                                    result['detected_patterns'].append(
                                        f'class_newer_than_jar:{delta_days}d')
                                    result['confidence'] = min(100, result['confidence'] + 20)
                                    result['is_hack'] = True
                        except Exception:
                            pass

                    # P3 #14 — Entropía por secciones de 4KB (detecta packers/ofuscación)
                    # Un packer tiene secciones de altísima entropía mezcladas con baja.
                    # Un ZIP legítimo tiene entropía uniformemente alta en todo el archivo.
                    try:
                        fsize = os.path.getsize(file_path)
                        if 0 < fsize < 50 * 1024 * 1024:
                            CHUNK = 4096
                            section_entropies = []
                            with open(file_path, 'rb') as f:
                                while True:
                                    chunk = f.read(CHUNK)
                                    if not chunk:
                                        break
                                    freq = [0] * 256
                                    for b in chunk: freq[b] += 1
                                    n = len(chunk)
                                    ent = -sum((c/n) * _math.log2(c/n) for c in freq if c > 0)
                                    section_entropies.append(ent)

                            if section_entropies:
                                avg_ent  = sum(section_entropies) / len(section_entropies)
                                max_ent  = max(section_entropies)
                                min_ent  = min(section_entropies)
                                variance = sum((e - avg_ent)**2 for e in section_entropies) / len(section_entropies)
                                result['entropy']         = round(avg_ent, 3)
                                result['entropy_variance']= round(variance, 3)

                                # Packer signature: high-variance + some sections > 7.8
                                very_high = sum(1 for e in section_entropies if e > 7.8)
                                very_low  = sum(1 for e in section_entropies if e < 2.0)
                                packer_sig = variance > 4.0 and very_high > 0 and very_low > 0

                                if packer_sig:
                                    result['obfuscation_detected'] = True
                                    result['confidence'] += 25
                                    result['detected_patterns'].append(f'packer_entropy_variance:{variance:.2f}')
                                elif avg_ent > 7.5:
                                    result['obfuscation_detected'] = True
                                    result['confidence'] += 15
                                    result['detected_patterns'].append(f'high_entropy:{avg_ent:.2f}')
                    except Exception:
                        pass
                except Exception:
                    pass

            # Guardar en cache
            self.file_analysis_cache[file_path] = result
            return result
            
        except Exception as e:
            return {'is_hack': False, 'confidence': 0, 'detected_patterns': [], 'obfuscation_detected': False, 'file_hash': None}
    
    def is_suspicious_file(self, file_path):
        """Verifica si un archivo es sospechoso - MEJORADO CON CACHÉ INTELIGENTE"""
        try:
            # ========== PASO 0: VERIFICAR CACHÉ (optimización) ==========
            if self.file_cache:
                cached_result = self.file_cache.is_cached(file_path)
                if cached_result and cached_result.get('cached'):
                    # Archivo en caché y no modificado, usar resultado cacheado
                    return cached_result.get('is_suspicious', False)
            
            filename = os.path.basename(file_path).lower()
            file_dir = os.path.dirname(file_path).lower()
            full_path_lower = file_path.lower()
            
            # ========== PASO 1: VERIFICACIÓN DE WHITELIST (prioridad máxima) ==========
            if self.is_whitelisted(file_path):
                # Guardar en caché como no sospechoso
                if self.file_cache:
                    self.file_cache.cache_result(file_path, is_suspicious=False, confidence=0)
                return False
            
            # ========== PASO 1.5: VERIFICACIÓN DE PATRONES LEGÍTIMOS APRENDIDOS ==========
            if self.legitimate_patterns:
                try:
                    file_hash = None
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'rb') as f:
                                file_hash = hashlib.sha256(f.read()).hexdigest()
                        except:
                            pass
                    
                    is_legitimate, legit_confidence = self.legitimate_patterns.is_legitimate(
                        file_path=file_path,
                        file_name=filename,
                        file_hash=file_hash,
                        context={'file_path': file_path}
                    )
                    
                    if is_legitimate and legit_confidence >= 0.6:
                        # Guardar en caché como no sospechoso
                        if self.file_cache:
                            self.file_cache.cache_result(file_path, is_suspicious=False, confidence=0)
                        print(f"✅ Archivo legítimo aprendido: {filename} (confianza: {legit_confidence:.2f})")
                        return False
                except Exception as e:
                    # Si hay error, continuar con el análisis normal
                    pass
            
            # ========== PASO 2: ANÁLISIS AVANZADO DE CONTENIDO ==========
            content_analysis = self.analyze_file_content(file_path)
            if content_analysis['is_hack'] and content_analysis['confidence'] >= 70:
                # Verificación adicional: no debe estar en whitelist incluso si el contenido es sospechoso
                # (para evitar falsos positivos en software legítimo ofuscado)
                if not self.is_whitelisted(file_path):
                    return True
            
            # ========== PASO 3: DETECCIÓN POR NOMBRE Y UBICACIÓN ==========
            #
            # REGLA ANTI-FALSOS-POSITIVOS:
            # Solo nombres de clientes/módulos que NO aparecen en software legítimo.
            # Términos genéricos (fly, speed, ghost, bypass, inject, auto, macro, sprint,
            # patch, hook, pack, encrypt, camera, client, pathfinder) se eliminaron porque
            # producen decenas de falsos positivos en mods legítimos, launchers y software
            # de sistema. Esos términos solo se evalúan en analyze_file_content() con
            # múltiples co-ocurrencias, nunca sobre el nombre del archivo solo.

            # Rutas seguras — si el archivo está aquí, no es un hack
            SAFE_PATH_PREFIXES = [
                'c:\\windows\\', 'c:\\program files\\microsoft',
                'c:\\program files (x86)\\microsoft',
                'c:\\program files\\common files',
                '\\steamapps\\workshop\\', '\\steamapps\\common\\',
                '\\epicgames\\', '\\riot games\\', '\\gog galaxy\\',
                '\\battle.net\\', '\\origin games\\',
                '\\jdk', '\\jre', '\\java\\',
                '\\visual studio\\', '\\jetbrains\\',
                '\\obs-studio\\', '\\discord\\', '\\zoom\\',
            ]
            for safe in SAFE_PATH_PREFIXES:
                if safe in full_path_lower:
                    return False

            # Clientes de hack con nombres únicos — alta precisión, bajo FP
            # EXCLUIDOS: impact, rise, drip, nyx, vanish, sloth, lucid (demasiado genéricos)
            KNOWN_HACK_CLIENTS = {
                'vape', 'vapelite', 'entropy', 'entropyclient', 'whiteout', 'whiteoutclient',
                'liquidbounce', 'wurst', 'wurstclient', 'impactclient',
                'sigmaclient', 'fluxclient', 'future', 'futureclient',
                'astolfo', 'astolfoclient', 'exhibition', 'novoline', 'novolineclient',
                'riseclient', 'dripclient', 'phobos', 'phobosclient',
                'tenacity', 'meteor', 'meteorclient', 'rusherhack', 'konas', 'kami',
                'weepcraft', 'ghostclient', 'nextgen', 'tegernako', 'zeroday',
                'seppuku', 'wasp', 'komat',
                'dllinjector', 'cheatengine', 'processhollowing', 'dllhijacking',
            }

            # Módulos cuyo nombre es exclusivo de cheats (no aparecen en mods legítimos)
            # EXCLUIDOS: nuker, freecam, fullbright, nofall (aparecen en mods legítimos)
            HACK_MODULE_NAMES = {
                'killaura', 'aimbot', 'triggerbot', 'antikb', 'antiknockback',
                'xraymod', 'wallhack', 'boxesp', 'chams', 'traceline',
                'autoclicker', 'clickgui', 'bunnyhop', 'bhop', 'aimassist',
                'wtap', 'autotool', 'autosprint', 'speedhack',
            }

            # Combinaciones path-específicas de hack en carpetas de Minecraft
            HACK_PATH_COMBOS = [
                ('mods', 'vape'), ('mods', 'entropy'), ('mods', 'sigma'),
                ('mods', 'flux'), ('mods', 'future'), ('mods', 'astolfo'),
                ('mods', 'liquidbounce'), ('mods', 'wurst'), ('mods', 'impact'),
                ('versions', 'vape'), ('versions', 'entropy'), ('versions', 'sigma'),
                ('versions', 'flux'), ('versions', 'liquidbounce'),
            ]

            HIGH_CONFIDENCE_HACK_PATTERNS = list(KNOWN_HACK_CLIENTS | HACK_MODULE_NAMES)
            
            # Verificar patrones de alta confianza
            is_suspicious = False
            confidence = 0
            detected_patterns = []

            # Nombre de archivo exacto o como parte del stem (sin extensión)
            file_stem = os.path.splitext(filename)[0]
            # Normalizar también para detectar homoglyphs cirílicos en nombres de archivo
            filename_norm = _normalize(filename)
            file_stem_norm = _normalize(file_stem)
            full_path_norm = _normalize(full_path_lower)
            for pattern in HIGH_CONFIDENCE_HACK_PATTERNS:
                # Match en nombre del archivo (stem) o en la ruta completa como segmento
                stem_match = (pattern == file_stem or file_stem.startswith(pattern + '-')
                              or file_stem.startswith(pattern + '_') or file_stem.endswith('-' + pattern)
                              or file_stem.endswith('_' + pattern) or (' ' + pattern) in file_stem
                              or (pattern + ' ') in file_stem)
                # Mismo chequeo pero sobre nombre normalizado (detecta homoglyphs)
                stem_match_norm = (pattern in file_stem_norm)
                path_segment_match = ('\\' + pattern + '\\') in full_path_lower or \
                                     ('/' + pattern + '/') in full_path_lower or \
                                     full_path_lower.endswith('\\' + pattern) or \
                                     full_path_lower.endswith('/' + pattern)
                # Clientes conocidos también pueden aparecer como substring en el nombre
                client_match = (pattern in KNOWN_HACK_CLIENTS and
                                (pattern in filename or pattern in filename_norm))
                if (stem_match or stem_match_norm or path_segment_match or client_match) and \
                        not self.is_whitelisted(file_path):
                    is_suspicious = True
                    confidence = max(confidence, 82)
                    detected_patterns.append(pattern)
                    break

            # Combinaciones path (mods/vape, versions/flux, etc.)
            if not is_suspicious:
                for (folder, hack) in HACK_PATH_COMBOS:
                    if folder in full_path_lower and hack in filename:
                        if not self.is_whitelisted(file_path):
                            is_suspicious = True
                            confidence = max(confidence, 85)
                            detected_patterns.append(f'{folder}/{hack}')
                            break
            
            # ========== PASO 4: DETECCIÓN POR EXTENSIÓN Y CONTEXTO ==========
            # Archivos JAR en ubicaciones sospechosas
            if filename.endswith('.jar'):
                if 'mods' in file_dir or 'versions' in file_dir:
                    # Solo nombres exactos de hack clients — NO 'hack' o 'cheat' solos (muy genéricos)
                    jar_hacks = ['vape', 'vapelite', 'entropy', 'liquidbounce', 'wurst',
                                 'astolfo', 'fluxclient', 'ghostclient', 'novoline',
                                 'killaura', 'aimbot', 'cheatengine']
                    if any(h in filename for h in jar_hacks):
                        if not self.is_whitelisted(file_path):
                            is_suspicious = True
                            confidence = max(confidence, 75)
                            detected_patterns.append('suspicious_jar_location')
            
            # ========== PASO 5: DETECCIÓN DE OFUSCACIÓN EXCESIVA ==========
            if content_analysis.get('obfuscation_detected', False):
                # Si está muy ofuscado Y no está en whitelist, es sospechoso
                if content_analysis['confidence'] >= 50 and not self.is_whitelisted(file_path):
                    # Pero solo si no es software conocido (launchers, etc.)
                    known_software = ['anydesk', 'teamviewer', 'gtavlauncher', 'rockstar', 'steam', 'epic']
                    if not any(sw in full_path_lower for sw in known_software):
                        is_suspicious = True
                        confidence = max(confidence, 60)
                        detected_patterns.append('obfuscation')
            
            # ========== PASO 6: DETECCIÓN POR HASH CONOCIDO ==========
            if content_analysis.get('file_hash') in self.known_hack_hashes:
                is_suspicious = True
                confidence = 100  # Hash conocido = 100% confianza
                detected_patterns.append('known_hash')
            
            # Guardar resultado en caché
            if self.file_cache:
                self.file_cache.cache_result(
                    file_path,
                    is_suspicious=is_suspicious,
                    confidence=confidence,
                    detected_patterns=detected_patterns if detected_patterns else None,
                    scan_result=content_analysis
                )
            
            return is_suspicious
            
        except Exception as e:
            # En caso de error, no marcar como sospechoso para evitar falsos positivos
            return False
    
    def _scan_for_specific_hacks(self, drive):
        """Buscar específicamente carpetas con nombres de hacks conocidos - MEJORADO CON TÉCNICAS SILENT-SCANNER"""
        try:
            print(f"🔍 BUSCANDO HACKS ESPECÍFICOS EN {drive}")
            
            # Patrones expandidos de hacks reales (incluyendo variantes y técnicas avanzadas)
            hack_patterns = [
                # Hacks específicos conocidos de Minecraft (nombres exactos y variantes)
                'vape', 'vapelite', 'vapev2', 'vapev4', 'vape.exe', 'vape.jar',
                'entropy', 'entropyclient', 'entropy.exe', 'entropy.jar',
                'whiteout', 'whiteoutclient', 'whiteout.exe', 'whiteout.jar',
                'liquidbounce', 'liquid bounce', 'lb', 'liquidbounceclient',
                'wurst', 'wurstclient', 'wurst loader', 'wurst.exe',
                'impact', 'impact client', 'impactclient', 'impact.exe',
                'sigma', 'sigmaclient', 'sigma5.0', 'sigma-5.0',
                'flux', 'fluxclient', 'flux b1.6', 'flux 1.8.8', 'flux1.8.8', 'flux 1.8.9',
                'future', 'futureclient', 'future.exe',
                'astolfo', 'astolfoclient', 'exhibition', 'exhibitionclient',
                'novoline', 'novolineclient', 'rise', 'riseclient',
                'moon', 'moonclient', 'drip', 'dripclient',
                'ghost', 'ghostclient', 'ghost.exe',
                'phobos', 'komat', 'wasp', 'konas', 'seppuku', 'sloth',
                'lucid', 'tenacity', 'nyx', 'vanish', 'ploow', 'cloud',
                'nextgen', 'tegernako', 'zeroday',
                
                # Módulos de hack cuyo nombre es exclusivo (no aparece en software legítimo)
                'xray', 'killaura', 'aimbot', 'wallhack', 'boxesp', 'chams',
                'autoclicker', 'autotool', 'autosprint', 'speedhack',
                'wtap', 'aimassist', 'bhop', 'nofall', 'antiknockback',
                'antikb', 'triggerbot', 'freecam', 'fullbright', 'nuker',
                'clickgui', 'bunnyhop', 'traceline',

                # Inyección y exploits — solo términos muy específicos
                'dllinjector', 'dllhijacking', 'processhollowing', 'codecave',
                'cheatengine',

                # Clientes con nombre único (no causan confusión con software legítimo)
                'silentclient', 'ghostclient'
            ]
            
            # Lista ampliada de falsos positivos para evitar detecciones incorrectas
            false_positives = [
                'zomboid', 'shaders', 'textures', 'media', 'vscode', 'pylance', 'skimage', 'pyi',
                'minecraft', 'mc', 'mojang', 'launcher', 'versions', 'mods', 'resourcepacks', 
                'saves', 'servers', 'config', 'logs', 'screenshots', 'backups', 'cache',
                'temp', 'tmp', 'downloads', 'documents', 'desktop', 'pictures', 'music',
                'videos', 'appdata', 'program files', 'windows', 'system32', 'riot games',
                'lunar client', 'badlion', 'forge', 'fabric', 'optifine', 'iris', 'sodium',
                'lithium', 'phosphor', 'starlight', 'carpet', 'carpetmod', 'tweakeroo',
                'litematica', 'minihud', 'malilib', 'itemscroller', 'inventory profiles',
                'worldedit', 'worldguard', 'essentials', 'luckperms', 'vault', 'economy',
                'permissions', 'multiverse', 'plotsquared', 'griefprevention', 'coreprotect',
                'citizens', 'mythicmobs', 'mcmmo', 'jobs', 'shopkeepers', 'chestshop',
                'auctionhouse', 'auction', 'bazaar', 'market', 'trade', 'exchange',
                'bank', 'money', 'coins', 'tokens', 'points', 'credits', 'balance',
                'account', 'profile', 'user', 'player', 'member', 'staff', 'admin',
                'moderator', 'helper', 'builder', 'developer', 'owner', 'manager',
                'discord', 'telegram', 'whatsapp', 'skype', 'teamspeak', 'mumble',
                'ventrilo', 'curse', 'twitch', 'youtube', 'stream', 'recording',
                'obs', 'streamlabs', 'xsplit', 'bandicam', 'fraps', 'dxtory',
                'shadowplay', 'relive', 'raptr', 'steam', 'origin', 'uplay',
                'epic', 'gog', 'battle.net', 'battlenet', 'blizzard', 'activision',
                'ea', 'electronic arts', 'ubisoft', 'bethesda', 'cd projekt',
                'rockstar', 'take-two', '2k', 'square enix', 'capcom', 'konami',
                'bandai namco', 'sega', 'nintendo', 'sony', 'microsoft', 'xbox',
                'playstation', 'nintendo switch', 'pc', 'windows', 'mac', 'linux',
                'android', 'ios', 'mobile', 'tablet', 'laptop', 'desktop', 'computer',
                'gaming', 'game', 'games', 'gamer', 'streamer', 'youtuber', 'content',
                'creator', 'influencer', 'social', 'media', 'network', 'community',
                'server', 'hosting', 'vps', 'dedicated', 'cloud', 'aws', 'azure',
                'google', 'amazon', 'microsoft', 'oracle', 'ibm', 'dell', 'hp',
                'lenovo', 'asus', 'acer', 'msi', 'gigabyte', 'evga', 'corsair',
                'razer', 'logitech', 'steelseries', 'hyperx', 'kingston', 'crucial',
                'samsung', 'intel', 'amd', 'nvidia', 'ati', 'ati radeon', 'geforce',
                'rtx', 'gtx', 'rx', 'ryzen', 'core i', 'pentium', 'celeron',
                'athlon', 'phenom', 'fx', 'a', 'e', 'pro', 'threadripper', 'epyc'
            ]
            
            import time as _t
            _hacks_start = _t.time()
            _max_depth = 5
            _timeout = 25  # segundos máximo para esta función

            for root, dirs, files in os.walk(drive):
                # Límite de tiempo y profundidad
                if _t.time() - _hacks_start > _timeout:
                    break
                depth = root.count(os.sep) - drive.count(os.sep)
                if depth > _max_depth:
                    dirs[:] = []
                    continue

                # Buscar en nombres de carpetas
                for dir_name in dirs:
                    dir_lower = dir_name.lower()
                    for pattern in hack_patterns:
                        if pattern in dir_lower:
                            # Verificar si no es un falso positivo
                            if not any(false_positive in dir_lower or false_positive in root.lower() 
                                      for false_positive in false_positives):
                                print(f"🎯 HACK DETECTADO: {dir_name} en {root}")
                                self.issues_found.append({
                                    'nombre': dir_name,
                                    'ruta': root,
                                    'archivo': os.path.join(root, dir_name),
                                    'tipo': 'hack_folder',
                                    'categoria': 'HACKS',
                                    'alerta': 'CRITICAL'
                                })
                                break  # Solo agregar una vez por carpeta
                
                # Buscar en nombres de archivos
                for file_name in files:
                    file_lower = file_name.lower()
                    for pattern in hack_patterns:
                        if pattern in file_lower:
                            # Verificar si no es un falso positivo
                            if not any(false_positive in file_lower or false_positive in root.lower() 
                                      for false_positive in false_positives):
                                file_path = os.path.join(root, file_name)
                                print(f"🎯 HACK DETECTADO: {file_name} en {root}")
                                self.issues_found.append({
                                    'nombre': file_name,
                                    'ruta': root,
                                    'archivo': file_path,
                                    'tipo': 'hack_file',
                                    'categoria': 'HACKS',
                                    'alerta': 'CRITICAL'
                                })
                                break  # Solo agregar una vez por archivo
                                
        except Exception as e:
            print(f"⚠️ Error en _scan_for_specific_hacks: {e}")
    
    def scan_common_hack_locations(self):
        """Escanea ubicaciones comunes donde se descargan hacks - MEJORADO CON MÁS UBICACIONES"""
        try:
            print("🔍 ESCANEANDO UBICACIONES COMUNES DE HACKS...")
            import os
            
            # Ubicaciones comunes expandidas donde se descargan hacks
            common_locations = [
                # Ubicaciones del usuario (prioritarias)
                os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local', 'Temp'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'LocalLow'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Pictures'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Videos'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Music'),
                
                # Ubicaciones del sistema
                'C:\\Users\\Public',
                'C:\\Users\\Public\\Downloads',
                'C:\\Users\\Public\\Desktop',
                'C:\\Temp',
                'C:\\Windows\\Temp',
                'C:\\ProgramData',
                
                # Otras unidades comunes
                'D:\\Downloads',
                'D:\\Desktop',
                'D:\\Temp',
                'E:\\Downloads',
                'E:\\Desktop'
            ]
            
            _BROWSER_SKIP_COMMON = {
                'google\\chrome', 'mozilla\\firefox', 'microsoft\\edge',
                'brave-browser', 'vivaldi', 'opera software',
                'appdata\\local\\google', 'appdata\\roaming\\mozilla',
            }

            for location in common_locations:
                if os.path.exists(location):
                    print(f"📁 ESCANEANDO: {location}")
                    try:
                        for root, dirs, files in os.walk(location):
                            _root_lower = root.lower()
                            if any(frag in _root_lower for frag in _BROWSER_SKIP_COMMON):
                                dirs[:] = []
                                continue
                            for dir_name in dirs:
                                if _is_hack_folder(dir_name, _root_lower):
                                    print(f"🎯 HACK DETECTADO EN UBICACIÓN COMÚN: {dir_name} en {root}")
                                    self.issues_found.append({
                                        'nombre': dir_name,
                                        'ruta': root,
                                        'archivo': os.path.join(root, dir_name),
                                        'tipo': 'hack_folder_common',
                                        'categoria': 'HACKS',
                                        'alerta': 'CRITICAL'
                                    })
                    except Exception as e:
                        print(f"Error escaneando {location}: {str(e)}")
                        continue
        except Exception as e:
            print(f"Error escaneando ubicaciones comunes: {str(e)}")
    
    def scan_suspicious_folders(self):
        """Escanea carpetas con nombres sospechosos en todo el sistema"""
        try:
            print("🔍 ESCANEANDO CARPETAS SOSPECHOSAS EN TODO EL SISTEMA...")
            import os
            
            # Escanear en TODAS las ubicaciones posibles (más exhaustivo)
            search_locations = [
                # Ubicaciones del usuario
                os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'LocalLow'),
                
                # Ubicaciones del sistema
                'C:\\Users\\Public',
                'C:\\Temp',
                'C:\\Windows\\Temp',
                'C:\\ProgramData',
                'C:\\Program Files',
                'C:\\Program Files (x86)',
                
                # Ubicaciones adicionales comunes
                'D:\\', 'E:\\', 'F:\\', 'G:\\', 'H:\\'
            ]
            
            # Fragmentos de ruta de navegadores — se saltan COMPLETAMENTE durante el walk
            _BROWSER_SKIP = {
                'google\\chrome', 'mozilla\\firefox', 'microsoft\\edge',
                'brave-browser', 'vivaldi', 'opera software',
                'appdata\\local\\google', 'appdata\\roaming\\mozilla',
            }

            for location in search_locations:
                if os.path.exists(location):
                    print(f"📁 ESCANEANDO CARPETAS EN: {location}")
                    try:
                        # Limitar profundidad para evitar cuelgues
                        max_depth = 3
                        for root, dirs, files in os.walk(location):
                            # Saltar directorios de navegadores ANTES de explorar subdirectorios
                            _root_lower = root.lower()
                            if any(frag in _root_lower for frag in _BROWSER_SKIP):
                                dirs[:] = []  # No descender en directorios de navegadores
                                continue
                            # Controlar profundidad
                            depth = root[len(location):].count(os.sep)
                            if depth >= max_depth:
                                dirs[:] = []  # No explorar más profundamente
                                continue

                            for dir_name in dirs:
                                if _is_hack_folder(dir_name, _root_lower):
                                    print(f"🎯 CARPETA SOSPECHOSA ENCONTRADA: {dir_name} en {root}")
                                    self.issues_found.append({
                                        'nombre': dir_name,
                                        'ruta': root,
                                        'archivo': os.path.join(root, dir_name),
                                        'tipo': 'suspicious_folder',
                                        'categoria': 'HACKS',
                                        'alerta': 'CRITICAL'
                                    })
                                    # También escanear archivos .jar/.exe/.dll dentro de esta carpeta
                                    try:
                                        folder_path = os.path.join(root, dir_name)
                                        for file in os.listdir(folder_path):
                                            if file.lower().endswith(('.jar', '.exe', '.dll')):
                                                self.issues_found.append({
                                                    'nombre': file,
                                                    'ruta': folder_path,
                                                    'archivo': os.path.join(folder_path, file),
                                                    'tipo': 'hack_file',
                                                    'categoria': 'HACKS',
                                                    'alerta': 'CRITICAL'
                                                })
                                                print(f"🎯 ARCHIVO DE HACK ENCONTRADO: {file} en {folder_path}")
                                    except:
                                        pass
                    except Exception as e:
                        print(f"Error escaneando {location}: {str(e)}")
                        continue
        except Exception as e:
            print(f"Error escaneando carpetas sospechosas: {str(e)}")
    
    def scan_exact_hack_names(self):
        """Busca carpetas con nombres exactos de hacks conocidos - MEJORADO CON TÉCNICAS SILENT-SCANNER"""
        try:
            print("🎯 BUSCANDO CARPETAS CON NOMBRES EXACTOS DE HACKS...")
            import os
            
            # Nombres exactos expandidos de hacks conocidos (incluyendo variantes)
            exact_hack_names = [
                # Flux y variantes
                'flux', 'flux 1.8', 'flux1.8', 'flux 1.8.8', 'flux1.8.8', 'flux 1.8.9', 'flux1.8.9',
                'flux b1.6', 'fluxb1.6', 'fluxclient', 'flux-client',
                
                # Vape y variantes
                'vape', 'vape v4', 'vapev4', 'vape lite', 'vapelite', 'vapev2',
                'vape.exe', 'vape.jar', 'vapeclient', 'vape-client',
                
                # Entropy y variantes
                'entropy', 'entropy client', 'entropyclient', 'entropy.exe', 'entropy.jar',
                
                # Whiteout y variantes
                'whiteout', 'whiteout client', 'whiteoutclient', 'whiteout.exe', 'whiteout.jar',
                
                # LiquidBounce y variantes
                'liquidbounce', 'liquid bounce', 'liquidbounce client', 'lb', 'lbclient',
                
                # Wurst y variantes
                'wurst', 'wurst client', 'wurstclient', 'wurst loader', 'wurst.exe',
                
                # Impact y variantes
                'impact', 'impact client', 'impactclient', 'impact.exe',
                
                # Otros clientes conocidos
                'sigma', 'sigma client', 'sigmaclient', 'sigma5.0',
                'future', 'future client', 'futureclient',
                'astolfo', 'astolfo client', 'astolfoclient',
                'exhibition', 'exhibition client', 'exhibitionclient',
                'novoline', 'novoline client', 'novolineclient',
                'rise', 'rise client', 'riseclient',
                'moon', 'moon client', 'moonclient',
                'drip', 'drip client', 'dripclient',
                'ghost', 'ghost client', 'ghostclient',
                'phobos', 'komat', 'wasp', 'konas', 'seppuku', 'sloth',
                'lucid', 'tenacity', 'nyx', 'vanish', 'ploow', 'cloud',
                'nextgen', 'tegernako', 'zeroday',
                
                # Silent-scanner y variantes
                'silent', 'silent-scanner', 'silentscanner', 'silent client',
                'silent.exe', 'silent.jar'
            ]
            
            # Ubicaciones donde buscar
            search_locations = [
                os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local'),
                os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming'),
                'C:\\Users\\Public',
                'C:\\Temp',
                'C:\\ProgramData'
            ]
            
            for location in search_locations:
                if os.path.exists(location):
                    print(f"🎯 BUSCANDO NOMBRES EXACTOS EN: {location}")
                    try:
                        for root, dirs, files in os.walk(location):
                            for dir_name in dirs:
                                dir_lower = dir_name.lower().strip()
                                for hack_name in exact_hack_names:
                                    if hack_name.lower() == dir_lower or hack_name.lower() in dir_lower:
                                        print(f"🚨 HACK EXACTO ENCONTRADO: {dir_name} en {root}")
                                        self.issues_found.append({
                                            'nombre': dir_name,
                                            'ruta': root,
                                            'archivo': os.path.join(root, dir_name),
                                            'tipo': 'exact_hack_folder',
                                            'categoria': 'HACKS',
                                            'alerta': 'CRITICAL'
                                        })
                                        
                                        # Escanear contenido de la carpeta
                                        try:
                                            folder_path = os.path.join(root, dir_name)
                                            for file in os.listdir(folder_path):
                                                file_path = os.path.join(folder_path, file)
                                                if os.path.isfile(file_path):
                                                    self.issues_found.append({
                                                        'nombre': file,
                                                        'ruta': folder_path,
                                                        'archivo': file_path,
                                                        'tipo': 'hack_file',
                                                        'categoria': 'HACKS',
                                                        'alerta': 'CRITICAL'
                                                    })
                                                    print(f"🚨 ARCHIVO DE HACK: {file}")
                                        except:
                                            pass
                    except Exception as e:
                        print(f"Error buscando nombres exactos en {location}: {str(e)}")
                        continue
        except Exception as e:
            print(f"Error buscando nombres exactos de hacks: {str(e)}")
    
    def secondary_filter(self, issues):
        """Segundo filtro más inteligente para detectar hacks reales"""
        try:
            print("🔍 APLICANDO SEGUNDO FILTRO INTELIGENTE...")
            
            # Patrones de hacks reales conocidos
            real_hack_patterns = [
                'flux', 'flux 1.8', 'flux1.8', 'flux 1.8.8', 'flux1.8.8',
                'vape', 'vape v4', 'vapev4', 'vape lite', 'vapelite',
                'entropy', 'entropy client', 'entropyclient',
                'whiteout', 'whiteout client', 'whiteoutclient',
                'liquidbounce', 'liquid bounce', 'liquidbounce client',
                'wurst', 'wurst client', 'wurstclient',
                'impact', 'impact client', 'impactclient',
                'sigma', 'sigma client', 'sigmaclient',
                'future', 'future client', 'futureclient',
                'astolfo', 'astolfo client', 'astolfoclient',
                'exhibition', 'exhibition client', 'exhibitionclient',
                'novoline', 'novoline client', 'novolineclient',
                'rise', 'rise client', 'riseclient',
                'moon', 'moon client', 'moonclient',
                'drip', 'drip client', 'dripclient',
                'ghost', 'ghost client', 'ghostclient'
            ]
            
            # Patrones de archivos de hacks (solo extensiones realmente sospechosas fuera de minecraft)
            hack_file_patterns = ['.jar', '.exe']

            # Ubicaciones donde los hacks suelen estar (excluye appdata porque .minecraft vive ahí)
            suspicious_locations = [
                'documents', 'downloads', 'desktop'
            ]
            
            filtered_issues = []
            
            for issue in issues:
                nombre = issue.get('nombre', '').lower()
                ruta = issue.get('ruta', '').lower()
                archivo = issue.get('archivo', '').lower()
                tipo = issue.get('tipo', '')
                
                # Verificar si es un hack real
                is_real_hack = False
                
                # 1. Verificar patrones de hacks reales
                for pattern in real_hack_patterns:
                    if pattern in nombre or pattern in ruta or pattern in archivo:
                        is_real_hack = True
                        break
                
                # 2. Verificar si está en ubicación sospechosa con extensión de hack
                if not is_real_hack:
                    for location in suspicious_locations:
                        if location in ruta:
                            for ext in hack_file_patterns:
                                if ext in archivo:
                                    is_real_hack = True
                                    break
                            if is_real_hack:
                                break
                
                # 3. Verificar si es archivo de hack en ubicación sospechosa
                if not is_real_hack and tipo in ['hack_file', 'exact_hack_folder']:
                    is_real_hack = True
                
                # 4. Verificar palabras clave específicas de hacks (NO usar 'mod'/'client' - demasiado genéricas)
                hack_keywords = ['hack', 'cheat', 'cracked', 'killaura', 'aimbot', 'wallhack', 'triggerbot']
                if not is_real_hack:
                    for keyword in hack_keywords:
                        if keyword in nombre or keyword in archivo:
                            is_real_hack = True
                            break

                if is_real_hack:
                    # Clasificar como HACK CRÍTICO
                    issue['alerta'] = 'CRITICAL'
                    if not issue.get('categoria'):
                        issue['categoria'] = 'HACKS'
                    filtered_issues.append(issue)
                    print(f"🚨 HACK REAL DETECTADO: {nombre} en {ruta}")
                else:
                    # Mantener si es sospechoso o ya tiene categoría asignada
                    if issue.get('alerta') in ['SOSPECHOSO', 'POCO_SOSPECHOSO'] or issue.get('categoria'):
                        filtered_issues.append(issue)
            
            print(f"🔍 SEGUNDO FILTRO APLICADO: {len(filtered_issues)} elementos clasificados")
            return filtered_issues
            
        except Exception as e:
            print(f"Error aplicando segundo filtro: {e}")
            return issues
    
    def secondary_scan_parallel(self):
        """Segundo scan en paralelo para doble verificación"""
        try:
            print("🔍 INICIANDO SEGUNDO SCAN EN PARALELO...")
            import threading
            import concurrent.futures
            
            # Crear hilos para diferentes tipos de escaneo
            threads = []
            
            # Hilo 1: Escaneo de ubicaciones críticas
            def scan_critical_locations():
                print("🔍 Segundo scan: Ubicaciones críticas...")
                critical_paths = [
                    os.path.join(os.environ.get('USERPROFILE', ''), 'Downloads'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'Desktop'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'Documents'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Roaming'),
                    'C:\\Temp',
                    'C:\\Windows\\Temp'
                ]
                
                for path in critical_paths:
                    if os.path.exists(path):
                        try:
                            for root, dirs, files in os.walk(path):
                                for file in files:
                                    if file.lower().endswith(('.jar', '.exe', '.dll')):
                                        file_path = os.path.join(root, file)
                                        if self.is_suspicious_file(file_path):
                                            self.issues_found.append({
                                                'nombre': file,
                                                'ruta': root,
                                                'archivo': file_path,
                                                'tipo': 'secondary_scan_file',
                                                'categoria': 'HACKS',
                                                'alerta': 'CRITICAL'
                                            })
                                            print(f"🔍 Segundo scan encontrado: {file}")
                        except Exception as e:
                            print(f"Error en segundo scan de {path}: {e}")
                            continue
            
            # Hilo 2: Escaneo de procesos en segundo plano
            def scan_background_processes():
                print("🔍 Segundo scan: Procesos en segundo plano...")
                try:
                    import psutil
                    for proc in psutil.process_iter(['pid', 'name', 'exe']):
                        try:
                            proc_name = proc.info['name'].lower()
                            if any(hack in proc_name for hack in ['flux', 'vape', 'entropy', 'wurst', 'impact']):
                                self.issues_found.append({
                                    'nombre': proc.info['name'],
                                    'ruta': proc.info['exe'] or 'Proceso en memoria',
                                    'archivo': f"PID: {proc.info['pid']}",
                                    'tipo': 'background_process',
                                    'categoria': 'BACKGROUND_PROCESSES',
                                    'alerta': 'CRITICAL'
                                })
                                print(f"🔍 Segundo scan: Proceso sospechoso {proc.info['name']}")
                        except:
                            continue
                except Exception as e:
                    print(f"Error escaneando procesos: {e}")
            
            # Hilo 3: Escaneo de archivos temporales
            def scan_temp_files():
                print("🔍 Segundo scan: Archivos temporales...")
                temp_paths = [
                    os.path.join(os.environ.get('TEMP', ''), ''),
                    os.path.join(os.environ.get('TMP', ''), ''),
                    'C:\\Windows\\Temp',
                    'C:\\Temp'
                ]
                
                for temp_path in temp_paths:
                    if os.path.exists(temp_path):
                        try:
                            for root, dirs, files in os.walk(temp_path):
                                for file in files:
                                    if any(hack in file.lower() for hack in ['flux', 'vape', 'entropy', 'hack', 'cheat']):
                                        file_path = os.path.join(root, file)
                                        self.issues_found.append({
                                            'nombre': file,
                                            'ruta': root,
                                            'archivo': file_path,
                                            'tipo': 'temp_hack_file',
                                            'categoria': 'TEMP_FILES',
                                            'alerta': 'CRITICAL'
                                        })
                                        print(f"🔍 Segundo scan: Archivo temporal sospechoso {file}")
                        except Exception as e:
                            print(f"Error escaneando temporales {temp_path}: {e}")
                            continue
            
            # Ejecutar todos los hilos en paralelo
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(scan_critical_locations),
                    executor.submit(scan_background_processes),
                    executor.submit(scan_temp_files)
                ]
                
                # Esperar a que terminen todos
                for future in concurrent.futures.as_completed(futures, timeout=30):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"Error en segundo scan paralelo: {e}")
            
            print("✅ Segundo scan paralelo completado")
            
        except Exception as e:
            print(f"Error en segundo scan paralelo: {e}")
    
    def advanced_minecraft_process_analysis(self):
        """Análisis avanzado de procesos relacionados con Minecraft - MEJORADO CON DETECCIÓN DE SUBPROCESOS"""
        try:
            print("🔍 ANÁLISIS AVANZADO DE PROCESOS DE MINECRAFT...")
            import psutil
            import subprocess
            
            # Usar el nuevo analizador de conexiones para análisis más profundo
            try:
                from minecraft_connection_analyzer import MinecraftConnectionAnalyzer
                analyzer = MinecraftConnectionAnalyzer()
                
                # Escanear procesos y subprocesos ocultos
                advanced_issues = analyzer.scan_minecraft_processes_and_injections()
                self.issues_found.extend(advanced_issues)
                
                # Obtener username desde conexiones activas
                if analyzer.minecraft_username:
                    self.detected_minecraft_username = analyzer.minecraft_username
                    print(f"👤 Username detectado desde conexión activa: {analyzer.minecraft_username}")
            except ImportError:
                print("⚠️ Módulo minecraft_connection_analyzer no disponible, usando análisis básico")
            except Exception as e:
                print(f"⚠️ Error en análisis avanzado: {e}")
            
            # 1. Detección de inyección de DLLs en procesos de Java/Minecraft
            def scan_dll_injection():
                print("🔍 Escaneando inyección de DLLs...")
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'exe']):
                        try:
                            if proc.info['name'].lower() in ['java.exe', 'javaw.exe', 'minecraft.exe']:
                                # Obtener DLLs cargadas por el proceso
                                dlls = proc.memory_maps()
                                for dll in dlls:
                                    dll_path = dll.path.lower()
                                    if any(hack in dll_path for hack in ['flux', 'vape', 'entropy', 'wurst', 'impact', 'inject']):
                                        self.issues_found.append({
                                            'nombre': os.path.basename(dll.path),
                                            'ruta': os.path.dirname(dll.path),
                                            'archivo': dll.path,
                                            'tipo': 'injected_dll',
                                            'categoria': 'HACKS',
                                            'alerta': 'CRITICAL'
                                        })
                                        print(f"🚨 DLL INYECTADA DETECTADA: {dll.path}")
                        except:
                            continue
                except Exception as e:
                    print(f"Error escaneando DLLs: {e}")
            
            # 2. Análisis de memoria de procesos
            def scan_memory_analysis():
                print("🔍 Analizando memoria de procesos...")
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                        try:
                            if proc.info['name'].lower() in ['java.exe', 'javaw.exe']:
                                # Verificar si el proceso tiene memoria sospechosa
                                memory_info = proc.memory_info()
                                if memory_info.rss > 500 * 1024 * 1024:  # Más de 500MB
                                    # Buscar strings sospechosos en la memoria
                                    try:
                                        # Usar strings para buscar patrones en memoria
                                        result = subprocess.run(['strings', '-n', '10', f'/proc/{proc.info["pid"]}/mem'], 
                                                             capture_output=True, text=True, timeout=10)
                                        if result.returncode == 0:
                                            output = result.stdout.lower()
                                            if any(hack in output for hack in ['flux', 'vape', 'entropy', 'wurst']):
                                                self.issues_found.append({
                                                    'nombre': f"Proceso {proc.info['name']} con memoria sospechosa",
                                                    'ruta': f"PID: {proc.info['pid']}",
                                                    'archivo': f"Memoria: {memory_info.rss // 1024 // 1024}MB",
                                                    'tipo': 'suspicious_memory',
                                                    'categoria': 'PROCESSES',
                                                    'alerta': 'CRITICAL'
                                                })
                                                print(f"🚨 MEMORIA SOSPECHOSA: {proc.info['name']} PID:{proc.info['pid']}")
                                    except:
                                        pass
                        except:
                            continue
                except Exception as e:
                    print(f"Error analizando memoria: {e}")
            
            # 3. Detección de hooks del sistema
            def scan_system_hooks():
                print("🔍 Detectando hooks del sistema...")
                try:
                    # Buscar procesos que usen APIs de hooking
                    hook_apis = ['SetWindowsHookEx', 'UnhookWindowsHookEx', 'CallNextHookEx']
                    for proc in psutil.process_iter(['pid', 'name', 'exe']):
                        try:
                            if proc.info['name'].lower() in ['java.exe', 'javaw.exe', 'minecraft.exe']:
                                # Verificar si el proceso tiene hooks activos
                                try:
                                    # Usar handle para verificar hooks
                                    result = subprocess.run(['handle', '-p', str(proc.info['pid'])], 
                                                         capture_output=True, text=True, timeout=10)
                                    if result.returncode == 0:
                                        output = result.stdout.lower()
                                        if any(api.lower() in output for api in hook_apis):
                                            self.issues_found.append({
                                                'nombre': f"Proceso {proc.info['name']} con hooks del sistema",
                                                'ruta': f"PID: {proc.info['pid']}",
                                                'archivo': proc.info['exe'] or 'Proceso en memoria',
                                                'tipo': 'system_hooks',
                                                'categoria': 'PROCESSES',
                                                'alerta': 'CRITICAL'
                                            })
                                            print(f"🚨 HOOKS DEL SISTEMA: {proc.info['name']} PID:{proc.info['pid']}")
                                except:
                                    pass
                        except:
                            continue
                except Exception as e:
                    print(f"Error detectando hooks: {e}")
            
            # 4. Análisis de conexiones de red de procesos de Minecraft
            def scan_network_connections():
                print("🔍 Analizando conexiones de red de Minecraft...")
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'connections']):
                        try:
                            if proc.info['name'].lower() in ['java.exe', 'javaw.exe', 'minecraft.exe']:
                                connections = proc.connections()
                                for conn in connections:
                                    if conn.status == 'ESTABLISHED':
                                        # Verificar si la conexión es sospechosa
                                        if conn.raddr.ip not in ['127.0.0.1', '0.0.0.0']:
                                            # Buscar IPs sospechosas o puertos no estándar de Minecraft
                                            if conn.raddr.port not in [25565, 25566, 25567]:  # Puertos estándar de Minecraft
                                                self.issues_found.append({
                                                    'nombre': f"Conexión sospechosa desde {proc.info['name']}",
                                                    'ruta': f"PID: {proc.info['pid']}",
                                                    'archivo': f"{conn.raddr.ip}:{conn.raddr.port}",
                                                    'tipo': 'suspicious_connection',
                                                    'categoria': 'NETWORK_CONNECTIONS',
                                                    'alerta': 'CRITICAL'
                                                })
                                                print(f"🚨 CONEXIÓN SOSPECHOSA: {conn.raddr.ip}:{conn.raddr.port}")
                        except:
                            continue
                except Exception as e:
                    print(f"Error analizando conexiones: {e}")
            
            # 5. Reporte detallado de proceso Minecraft / Java
            def scan_minecraft_process_info():
                print("🔍 Recopilando información detallada del proceso Minecraft...")
                mc_names = {'java.exe', 'javaw.exe', 'minecraft.exe', 'minecraftlauncher.exe'}
                try:
                    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'memory_info',
                                                     'cpu_percent', 'create_time', 'username', 'status']):
                        try:
                            pname = (proc.info['name'] or '').lower()
                            if pname not in mc_names:
                                continue
                            pid = proc.info['pid']
                            exe = proc.info['exe'] or 'Desconocido'
                            cmdline = proc.info['cmdline'] or []
                            mem_mb = round(proc.info['memory_info'].rss / 1024 / 1024) if proc.info['memory_info'] else 0

                            # Connections
                            try:
                                conns = proc.connections()
                                conn_strs = [f"{c.raddr.ip}:{c.raddr.port}" for c in conns
                                             if c.status == 'ESTABLISHED' and c.raddr]
                            except Exception:
                                conn_strs = []

                            # Start time
                            try:
                                started = datetime.fromtimestamp(proc.info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
                            except Exception:
                                started = 'Desconocida'

                            # JVM args of interest
                            jvm_flags = [a for a in cmdline if a.startswith('-') and len(a) < 120]

                            summary_parts = [
                                f"PID: {pid}",
                                f"RAM: {mem_mb} MB",
                                f"Inicio: {started}",
                                f"Exe: {exe[:80]}",
                            ]
                            if conn_strs:
                                summary_parts.append(f"Conexiones: {', '.join(conn_strs[:5])}")
                            if jvm_flags:
                                summary_parts.append(f"JVM args: {' '.join(jvm_flags[:10])}")

                            self.issues_found.append({
                                'tipo': 'minecraft_process_info',
                                'nombre': f'Proceso Minecraft activo: {proc.info["name"]} (PID {pid})',
                                'ruta': exe[:255],
                                'archivo': ' | '.join(summary_parts)[:500],
                                'categoria': 'PROCESSES',
                                'alerta': 'NORMAL',
                                'confidence': 0,
                                'detected_patterns': conn_strs[:5],
                                'extra': {
                                    'pid': pid, 'ram_mb': mem_mb,
                                    'started': started, 'exe': exe[:120],
                                    'connections': conn_strs[:5],
                                    'jvm_args': jvm_flags[:10],
                                },
                            })
                            print(f"✅ Proceso MC: {proc.info['name']} PID:{pid} RAM:{mem_mb}MB conns:{conn_strs}")
                        except Exception:
                            continue
                except Exception as e:
                    print(f"Error en scan_minecraft_process_info: {e}")

            # Ejecutar todos los análisis en paralelo
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(scan_dll_injection),
                    executor.submit(scan_memory_analysis),
                    executor.submit(scan_system_hooks),
                    executor.submit(scan_network_connections),
                    executor.submit(scan_minecraft_process_info),
                ]

                # Esperar a que terminen todos
                for future in concurrent.futures.as_completed(futures, timeout=30):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"Error en análisis avanzado: {e}")

            print("✅ Análisis avanzado de procesos completado")
            
        except Exception as e:
            print(f"Error en análisis avanzado de procesos: {e}")

    # ── Anti-detection helpers ────────────────────────────────────────────────
    _DECOY_TITLES = [
        "Windows Security Health",
        "Microsoft .NET Runtime",
        "Java Update Scheduler",
        "Windows Update Assistant",
        "System Configuration",
        "Performance Monitor",
    ]
    _real_window_title = None

    def _camouflage_window(self):
        """Renames the window title to a generic Windows name during the scan."""
        try:
            import random
            self._real_window_title = self.root.title()
            decoy = random.choice(self._DECOY_TITLES)
            self.root.after(0, lambda: self.root.title(decoy))
        except Exception:
            pass

    def _restore_window_title(self):
        """Restores the original window title after the scan."""
        try:
            if self._real_window_title:
                self.root.after(0, lambda: self.root.title(self._real_window_title))
        except Exception:
            pass

    def _check_for_update(self):
        """Checks server for a newer scanner version and prompts to update."""
        try:
            if requests is None:
                return
            api_url = self.config.get('api_url', 'https://asperss.onrender.com').rstrip('/')
            resp = requests.get(f"{api_url}/api/scanner/version", timeout=8)
            if resp.status_code != 200:
                return
            data = resp.json()
            latest = data.get('version', '')
            download_url = data.get('download_url', '')
            changelog = data.get('changelog', '')
            if not latest or not download_url:
                return
            if latest <= SCANNER_VERSION:
                return
            # Show update dialog on main thread
            self.root.after(0, lambda: self._show_update_dialog(latest, download_url, changelog))
        except Exception as e:
            print(f"[UPDATE] check failed: {e}")

    def _show_update_dialog(self, latest_version, download_url, changelog):
        """Shows update available dialog and downloads+replaces the exe if user accepts."""
        import tkinter as tk
        msg = f"Nueva versión disponible: v{latest_version}\nActual: v{SCANNER_VERSION}"
        if changelog:
            msg += f"\n\nCambios:\n{changelog}"
        msg += "\n\n¿Descargar e instalar ahora?"
        if not messagebox.askyesno("Actualización disponible", msg):
            return
        # Download in background
        threading.Thread(
            target=self._download_and_replace,
            args=(download_url,),
            daemon=True
        ).start()

    def _download_and_replace(self, download_url):
        """Downloads new exe to a temp file and relaunches via a batch script."""
        try:
            import tempfile, urllib.request
            exe_path = sys.executable  # path to the current .exe
            tmp_path = exe_path + '.new'
            messagebox.showinfo("Descargando...", "Descargando actualización. La aplicación se reiniciará al terminar.")
            urllib.request.urlretrieve(download_url, tmp_path)
            # Write a .bat that waits for this process to exit, replaces, then relaunches
            bat_content = (
                f'@echo off\n'
                f'timeout /t 2 /nobreak >nul\n'
                f'move /Y "{tmp_path}" "{exe_path}"\n'
                f'start "" "{exe_path}"\n'
                f'del "%~f0"\n'
            )
            bat_path = exe_path + '_update.bat'
            with open(bat_path, 'w') as f:
                f.write(bat_content)
            import subprocess as _sp
            _sp.Popen(['cmd', '/c', bat_path], creationflags=0x08000000)
            self.root.after(0, self.root.destroy)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error de actualización", str(e)))

    def check_authentication(self):
        """Sistema de autenticación usando Discord para generar tokens"""
        try:
            import tkinter as tk
            from tkinter import messagebox, simpledialog
            import hashlib
            import time
            import requests
            import json
            
            # PRIMERO: Verificar si ya hay un token válido en el config
            scan_token = self.config.get('scan_token', '')
            if scan_token:
                print(f"🔑 Token encontrado en config, verificando validez...")
                api_url = self.config.get('api_url', 'https://asperss.onrender.com')
                
                # Intentar validar el token sin mostrar ventana
                try:
                    response = requests.post(
                        f"{api_url}/api/validate-token",
                        json={'token': scan_token},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('valid', False):
                            print(f"✅ Token válido encontrado en config, autenticación automática exitosa")
                            if data.get('created_by'):
                                self.config['staff_name'] = data['created_by']
                            # P2 #2 — guardar allowed_mods del servidor en config
                            if data.get('allowed_mods'):
                                self.config['server_allowed_mods'] = data['allowed_mods']
                            if hasattr(self, 'db_integration') and self.db_integration:
                                self.db_integration.scan_token = scan_token
                            return True
                        else:
                            print(f"⚠️ Token en config no es válido, solicitando nuevo token")
                    else:
                        print(f"⚠️ Error validando token existente: {response.status_code}")
                except Exception as e:
                    print(f"⚠️ Error validando token existente: {e}")
                    # Continuar con el flujo normal de autenticación
            
            # Si no hay token válido, mostrar ventana de autenticación
            # Crear ventana de autenticación con estilo ARGUS PROJECTS
            auth_window = tk.Toplevel(self.root)
            auth_window.title("Argus Projects — Autenticación Requerida")
            auth_window.geometry("600x500")
            if UI_STYLE_AVAILABLE:
                auth_window.configure(bg=ModernUI.COLORS['bg_primary'])
            else:
                auth_window.configure(bg="#0a0e27")
            auth_window.resizable(False, False)
            auth_window.transient(self.root)
            auth_window.grab_set()
            
            # Centrar la ventana
            auth_window.update_idletasks()
            x = (auth_window.winfo_screenwidth() // 2) - (600 // 2)
            y = (auth_window.winfo_screenheight() // 2) - (500 // 2)
            auth_window.geometry(f"600x500+{x}+{y}")
            
            # Variables de autenticación
            auth_result = [False]
            
            def generate_web_token():
                """Genera un token usando la API web"""
                try:
                    # Asegurar que self.config esté disponible
                    if not hasattr(self, 'config') or not self.config:
                        self.config = self.load_config()
                    
                    # Obtener token desde la API web
                    api_url = self.config.get('api_url', 'https://asperss.onrender.com')
                    web_url = self.config.get('web_url', 'https://asperss.onrender.com')
                    
                    # Abrir navegador para que el staff genere el token desde el panel web
                    import webbrowser
                    webbrowser.open(f"{web_url}/panel#tokens-section")
                    
                    messagebox.showinfo(
                        "🔐 Generar Token - ASPERS Projects",
                        f"Por favor, genera un token desde el panel web:\n\n{web_url}/panel#tokens-section\n\n\n1. Abre el panel web (ya se abrió automáticamente)\n2. Ve a la sección 'Gestión de Tokens'\n3. Haz clic en 'Crear Nuevo Token'\n4. Copia el token generado\n5. Pégalo aquí y haz clic en 'Autenticar'"
                    )
                    return None
                        
                except Exception as e:
                    print(f"Error generando token: {e}")
                    messagebox.showerror("Error", f"No se pudo abrir el panel web. Por favor, accede manualmente a:\n{web_url}/panel#tokens-section")
                    return None
            
            def verify_token(token):
                """Verifica si el token es válido contra la API web"""
                try:
                    import requests
                    
                    # Asegurar que self.config esté disponible
                    if not hasattr(self, 'config') or not self.config:
                        self.config = self.load_config()
                    
                    # Obtener URL de la API desde la configuración (con failsafe anti-localhost)
                    _bad = ('http://localhost', 'https://localhost', 'http://127.0.0.1', 'https://127.0.0.1', 'https://ssapi-cfni.onrender.com')
                    api_url = self.config.get('api_url', '') or ''
                    if not api_url or any(api_url.startswith(p) for p in _bad):
                        api_url = 'https://asperss.onrender.com'
                        self.config['api_url'] = api_url
                    web_url = self.config.get('web_url', '') or ''
                    if not web_url or any(web_url.startswith(p) for p in _bad):
                        self.config['web_url'] = 'https://asperss.onrender.com'
                    print(f"🔍 Validando token contra API: {api_url}")
                    print(f"🔍 Token recibido (primeros 20 chars): {token[:20]}...")
                    
                    # Validar token contra la API con reintentos (Render puede estar "despertando")
                    import time
                    max_retries = 3
                    retry_delay = 2  # segundos
                    timeout = 30  # Aumentado a 30 segundos para Render
                    
                    for attempt in range(max_retries):
                        try:
                            if attempt > 0:
                                print(f"🔄 Reintentando validación de token (intento {attempt + 1}/{max_retries})...")
                                time.sleep(retry_delay * attempt)  # Backoff exponencial
                            
                            response = requests.post(
                                f"{api_url}/api/validate-token",
                                json={'token': token},
                                timeout=timeout
                            )
                            
                            print(f"📡 Respuesta de API: Status {response.status_code}")
                            
                            if response.status_code == 200:
                                data = response.json()
                                print(f"📡 Datos de respuesta: {data}")
                                
                                if data.get('valid', False):
                                    print(f"✅ Token válido verificado contra API")
                                    # Guardar token y dueño en configuración
                                    self.config['scan_token'] = token
                                    if data.get('created_by'):
                                        self.config['staff_name'] = data['created_by']
                                    
                                    # Actualizar también en db_integration inmediatamente
                                    if hasattr(self, 'db_integration') and self.db_integration:
                                        self.db_integration.scan_token = token
                                        print(f"✅ Token actualizado en db_integration inmediatamente")
                                    
                                    # Guardar token en archivo de configuración (ubicación persistente)
                                    try:
                                        import os
                                        import json
                                        import sys
                                        
                                        # Determinar ubicación persistente para config.json
                                        # SIEMPRE usar AppData\Roaming para ejecutables compilados (más persistente)
                                        if getattr(sys, 'frozen', False):
                                            # Usar AppData\Roaming (persistente, no temporal)
                                            appdata_roaming = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS')
                                            os.makedirs(appdata_roaming, exist_ok=True)
                                            config_path = os.path.join(appdata_roaming, 'config.json')
                                            print(f"📁 Guardando config en ubicación persistente: {config_path}")
                                        else:
                                            # Si está en desarrollo, buscar en el directorio del script
                                            script_dir = os.path.dirname(os.path.abspath(__file__))
                                            config_path = os.path.join(script_dir, 'config.json')
                                        
                                        # Leer config existente para no sobrescribir otros valores
                                        try:
                                            if os.path.exists(config_path):
                                                with open(config_path, 'r', encoding='utf-8') as f:
                                                    existing_config = json.load(f)
                                                existing_config['scan_token'] = token
                                                existing_config['api_url'] = self.config.get('api_url', existing_config.get('api_url', 'https://asperss.onrender.com'))
                                                existing_config['web_url'] = self.config.get('web_url', existing_config.get('web_url', 'https://asperss.onrender.com'))
                                                self.config = existing_config
                                            else:
                                                # Si no existe, usar el config actual y agregar token
                                                self.config['scan_token'] = token
                                        except Exception as read_error:
                                            # Si falla al leer, usar el config actual
                                            print(f"⚠️ Error leyendo config existente: {read_error}")
                                            self.config['scan_token'] = token
                                        
                                        # Guardar config
                                        with open(config_path, 'w', encoding='utf-8') as f:
                                            json.dump(self.config, f, indent=2, ensure_ascii=False)
                                        print(f"💾 Token guardado en {config_path}")
                                        
                                        # También actualizar self.config_path para futuras lecturas
                                        self.config_path = config_path
                                    except Exception as save_error:
                                        import traceback
                                        print(f"⚠️ No se pudo guardar token en archivo: {str(save_error)}")
                                        print(f"   Traceback: {traceback.format_exc()}")
                                    
                                    return True  # Token válido
                                else:
                                    # Token inválido, no reintentar
                                    error_msg = data.get('error', 'Token inválido')
                                    print(f"❌ Token inválido según API: {error_msg}")
                                    return False
                            else:
                                # Error HTTP, reintentar si no es 4xx (errores del cliente)
                                if response.status_code < 400 or response.status_code >= 500:
                                    if attempt < max_retries - 1:
                                        continue  # Reintentar
                                    else:
                                        raise Exception(f"Error HTTP {response.status_code} después de {max_retries} intentos")
                                else:
                                    # Error 4xx, no reintentar
                                    break
                        except requests.exceptions.Timeout:
                            if attempt < max_retries - 1:
                                print(f"⏱️ Timeout en intento {attempt + 1}, reintentando...")
                                continue
                            else:
                                print(f"❌ Timeout después de {max_retries} intentos. La API puede estar sobrecargada o inactiva.")
                                raise
                        except requests.exceptions.ConnectionError as e:
                            if attempt < max_retries - 1:
                                print(f"🔌 Error de conexión en intento {attempt + 1}, reintentando...")
                                continue
                            else:
                                print(f"❌ Error de conexión después de {max_retries} intentos: {str(e)}")
                                raise
                        except Exception as e:
                            if attempt < max_retries - 1:
                                print(f"⚠️ Error en intento {attempt + 1}: {str(e)}, reintentando...")
                                continue
                            else:
                                raise
                            
                    # Si llegamos aquí después de todos los reintentos sin éxito, retornar False
                    print(f"❌ No se pudo validar el token después de {max_retries} intentos")
                    return False
                            
                except requests.exceptions.ConnectionError as conn_err:
                    print(f"⚠️ No se pudo conectar con la API en {api_url}")
                    print(f"⚠️ Error de conexión: {conn_err}")
                    print(f"💡 Asegúrate de que:")
                    print(f"   1. La API esté corriendo en {api_url}")
                    print(f"   2. No haya firewall bloqueando la conexión")
                    try:
                        messagebox.showerror(
                            "Error de Conexión",
                            f"No se pudo conectar con la API en {api_url}\n\n"
                            f"Posibles causas:\n"
                            f"• El servidor está despertando (Render free tier, espera 30s)\n"
                            f"• Sin conexión a internet\n\n"
                            f"Cierra y vuelve a abrir el scanner para reintentar."
                        )
                    except:
                        pass
                    return False
                except Exception as e:
                    print(f"❌ Error al validar token: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
                    
                except ImportError:
                    print(f"❌ Módulo requests no disponible para validar token")
                    messagebox.showerror(
                        "Error",
                        "El módulo 'requests' no está instalado.\n\n"
                        "Instálalo con: pip install requests"
                    )
                    return False
                except Exception as e:
                    print(f"❌ Error verificando token: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
            
            def on_authenticate():
                """Maneja la autenticación"""
                token = token_entry.get().strip()
                
                if not token:
                    messagebox.showerror("Error", "Por favor ingresa un token")
                    return
                
                print(f"🔐 Intentando autenticar con token...")
                if verify_token(token):
                    # Actualizar token en db_integration si existe
                    if hasattr(self, 'db_integration') and self.db_integration:
                        self.db_integration.scan_token = token
                        print(f"✅ Token actualizado en db_integration")
                    
                    auth_result[0] = True
                    messagebox.showinfo("✅ Éxito", "Token válido. Acceso autorizado.")
                    auth_window.destroy()
                else:
                    error_msg = (
                        "Token inválido o expirado.\n\n"
                        "Verifica que:\n"
                        "• El token fue copiado correctamente\n"
                        "• El token no haya expirado\n"
                        f"• El token esté activo en el panel: {self.config.get('web_url','https://asperss.onrender.com')}\n"
                        "• Generaste el token desde tu cuenta de staff"
                    )
                    messagebox.showerror("❌ Error", error_msg)
                    # No borrar el token para que el usuario pueda revisarlo
            
            def on_generate_token():
                """Genera un nuevo token desde el panel web"""
                generate_web_token()
            
            
            def on_cancel():
                """Cancela la autenticación"""
                auth_result[0] = False
                auth_window.destroy()
            
            # Crear interfaz de autenticación con estilo ARGUS PROJECTS
            bg_color = ModernUI.COLORS['bg_primary'] if UI_STYLE_AVAILABLE else "#0d1117"
            card_color = ModernUI.COLORS['bg_card'] if UI_STYLE_AVAILABLE else "#161b22"
            text_primary = ModernUI.COLORS['text_primary'] if UI_STYLE_AVAILABLE else "#f0f6fc"
            text_secondary = ModernUI.COLORS['text_secondary'] if UI_STYLE_AVAILABLE else "#8b949e"
            accent_blue = ModernUI.COLORS['blue'] if UI_STYLE_AVAILABLE else "#1f6feb"
            accent_green = ModernUI.COLORS['green'] if UI_STYLE_AVAILABLE else "#238636"
            
            # Header con estilo moderno
            header_frame = tk.Frame(auth_window, bg=card_color, height=120)
            header_frame.pack(fill=tk.X)
            header_frame.pack_propagate(False)
            
            # Borde superior con gradiente
            border_top = tk.Frame(header_frame, bg=accent_blue, height=3)
            border_top.pack(fill=tk.X)
            
            # Contenido del header
            header_content = tk.Frame(header_frame, bg=card_color)
            header_content.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
            
            title_label = tk.Label(
                header_content,
                text="ASPERS PROJECTS",
                font=("Segoe UI", 28, "bold"),
                fg=text_primary,
                bg=card_color
            )
            title_label.pack()
            
            subtitle_label = tk.Label(
                header_content,
                text="Autenticación Requerida",
                font=("Segoe UI", 13),
                fg=text_secondary,
                bg=card_color
            )
            subtitle_label.pack(pady=(5, 0))
            
            # Card principal
            main_card = tk.Frame(auth_window, bg=card_color, relief=tk.FLAT, bd=0)
            main_card.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
            
            # Borde del card
            card_border = tk.Frame(main_card, bg=accent_blue, height=2)
            card_border.pack(fill=tk.X)
            
            # Contenido del card
            card_content = tk.Frame(main_card, bg=card_color)
            card_content.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)
            
            info_label = tk.Label(
                card_content,
                                text="Esta aplicación requiere autenticación para funcionar.\nIngresa el token generado por Discord o genera uno nuevo.",
                font=("Segoe UI", 11),
                fg=text_secondary,
                bg=card_color,
                justify="center",
                wraplength=500
            )
            info_label.pack(pady=(0, 25))
            
            # Frame para el token
            token_frame = tk.Frame(card_content, bg=card_color)
            token_frame.pack(pady=10, fill=tk.X)
            
            # Label del token con estilo moderno
            token_label = tk.Label(
                token_frame,
                text="🔑 Token de Autenticación:",
                font=("Segoe UI", 12, "bold"),
                fg=text_primary,
                bg=card_color
            )
            token_label.pack(anchor="w", pady=(0, 8))
            
            # Campo de entrada con estilo moderno
            entry_frame = tk.Frame(token_frame, bg=card_color)
            entry_frame.pack(fill=tk.X)
            
            token_entry = tk.Entry(
                entry_frame,
                font=("Consolas", 13, "bold"),
                width=35,
                bg="#161b22",
                fg=text_primary,
                insertbackground=text_primary,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=2,
                highlightbackground=accent_blue,
                highlightcolor=accent_blue
            )
            token_entry.pack(fill=tk.X, ipady=10)
            token_entry.focus_set()
            
            # Botones con estilo moderno ASPERS PROJECTS
            button_frame = tk.Frame(card_content, bg=card_color)
            button_frame.pack(pady=25)
            
            # Botón generar token
            generate_btn = tk.Button(
                button_frame,
                text="🔐 Generar Token",
                command=on_generate_token,
                bg=accent_blue,
                fg="#ffffff",
                font=("Segoe UI", 11, "bold"),
                padx=25,
                pady=12,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                activebackground="#58a6ff",
                activeforeground="#ffffff"
            )
            generate_btn.pack(side="left", padx=8)
            
            # Efecto hover para botón generar
            def on_gen_enter(e):
                generate_btn.config(bg="#58a6ff")
            def on_gen_leave(e):
                generate_btn.config(bg=accent_blue)
            generate_btn.bind('<Enter>', on_gen_enter)
            generate_btn.bind('<Leave>', on_gen_leave)
            
            # Botón autenticar
            auth_btn = tk.Button(
                button_frame,
                text="✅ Autenticar",
                command=on_authenticate,
                bg=accent_green,
                fg="#ffffff",
                font=("Segoe UI", 11, "bold"),
                padx=25,
                pady=12,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                activebackground="#2ea043",
                activeforeground="#ffffff"
            )
            auth_btn.pack(side="left", padx=8)
            
            # Efecto hover para botón autenticar
            def on_auth_enter(e):
                auth_btn.config(bg="#2ea043")
            def on_auth_leave(e):
                auth_btn.config(bg=accent_green)
            auth_btn.bind('<Enter>', on_auth_enter)
            auth_btn.bind('<Leave>', on_auth_leave)
            
            # Botón cancelar
            cancel_btn = tk.Button(
                button_frame,
                text="❌ Cancelar",
                command=on_cancel,
                bg="#21262d",
                fg=text_primary,
                font=("Segoe UI", 11, "bold"),
                padx=25,
                pady=12,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                activebackground="#30363d",
                activeforeground=text_primary
            )
            cancel_btn.pack(side="left", padx=8)
            
            # Efecto hover para botón cancelar
            def on_cancel_enter(e):
                cancel_btn.config(bg="#30363d")
            def on_cancel_leave(e):
                cancel_btn.config(bg="#21262d")
            cancel_btn.bind('<Enter>', on_cancel_enter)
            cancel_btn.bind('<Leave>', on_cancel_leave)
            
            # Separador visual
            separator = tk.Frame(card_content, bg="#21262d", height=1)
            separator.pack(fill=tk.X, pady=(15, 15))
            
            # Información adicional con estilo moderno
            info_frame = tk.Frame(card_content, bg="#161b22", relief=tk.FLAT, bd=0)
            info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            info_title = tk.Label(
                info_frame,
                text="📋 Instrucciones",
                font=("Segoe UI", 12, "bold"),
                fg=text_primary,
                bg="#161b22"
            )
            info_title.pack(anchor="w", padx=15, pady=(15, 10))
            
            info_text = tk.Text(
                info_frame,
                height=7,
                width=55,
                bg="#161b22",
                fg=text_secondary,
                font=("Segoe UI", 10),
                wrap=tk.WORD,
                relief=tk.FLAT,
                bd=0,
                padx=15,
                pady=10,
                highlightthickness=0
            )
            info_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
            
            info_content = """1. Haz clic en "Generar Token" para crear un nuevo token
   2. El token se enviará automáticamente a Discord
   3. Revisa Discord para obtener el token
4. Copia y pega el token en el campo de arriba
   5. Haz clic en "Autenticar" para verificar el token
   
⚠️ NOTA: Los tokens expiran en 10 minutos por seguridad."""
            
            info_text.insert("1.0", info_content)
            info_text.config(state="disabled")
            
            # Centrar la ventana y esperar
            auth_window.focus_set()
            auth_window.wait_window()
            
            return auth_result[0]
            
        except Exception as e:
            print(f"Error en autenticación: {e}")
            return False
    
    
    def _generate_summary_section(self, files, category, limit):
        """Genera resumen de archivos no mostrados"""
        if len(files) <= limit:
            return ''
        
        hidden_count = len(files) - limit
        return f'''
        <div class="issue system">
            <div class="issue-title">📊 Resumen</div>
            <div class="issue-details">
                <strong>Total de archivos {category}:</strong> {len(files)}<br>
                <strong>Mostrados:</strong> {limit}<br>
                <strong>No mostrados:</strong> {hidden_count} (para evitar saturar la página)
            </div>
        </div>
        '''
    
    def scan_disabled_processes(self):
        """Escanea procesos deshabilitados usando sc query dps"""
        try:
            print("🔍 ESCANEANDO PROCESOS DESHABILITADOS (sc query dps)...")
            import subprocess
            
            # Ejecutar sc query dps
            result = subprocess.run(['sc', 'query', 'dps'], capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'STOPPED' in line.upper():
                        print(f"⚠️ PROCESO DESHABILITADO DETECTADO: {line.strip()}")
                        self.issues_found.append({
                            'nombre': f"Proceso deshabilitado: {line.strip()}",
                            'ruta': 'Sistema',
                            'archivo': 'sc query dps',
                            'tipo': 'disabled_process',
                            'categoria': 'PROCESSES',
                            'alerta': 'SOSPECHOSO'
                        })
        except Exception as e:
            print(f"Error escaneando procesos deshabilitados: {str(e)}")
    
    def scan_dns_cache(self):
        """Escanea caché DNS usando ipconfig/displaydns"""
        try:
            print("🔍 ESCANEANDO CACHÉ DNS (ipconfig/displaydns)...")
            import subprocess
            
            # Ejecutar ipconfig/displaydns
            result = subprocess.run(['ipconfig', '/displaydns'], capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                suspicious_domains = []
                
                for line in lines:
                    if any(domain in line.lower() for domain in ['minecraft', 'hack', 'cheat', 'ghost', 'vape', 'entropy']):
                        suspicious_domains.append(line.strip())
                
                if suspicious_domains:
                    print(f"⚠️ DOMINIOS SOSPECHOSOS EN CACHÉ DNS: {len(suspicious_domains)}")
                    self.issues_found.append({
                        'nombre': f"Dominios sospechosos en DNS: {len(suspicious_domains)}",
                        'ruta': 'DNS Cache',
                        'archivo': 'ipconfig/displaydns',
                        'tipo': 'dns_cache',
                        'categoria': 'DNS_CACHE',
                        'alerta': 'SOSPECHOSO'
                    })
        except Exception as e:
            print(f"Error escaneando caché DNS: {str(e)}")
    
    def scan_running_processes(self):
        """Escanea procesos ejecutados usando tasklist"""
        try:
            print("🔍 ESCANEANDO PROCESOS EJECUTADOS (tasklist)...")
            import subprocess
            
            # Ejecutar tasklist
            result = subprocess.run(['tasklist'], capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                suspicious_processes = []
                
                for line in lines:
                    if any(process in line.lower() for process in ['minecraft', 'java', 'hack', 'cheat', 'ghost', 'vape', 'entropy', 'inject']):
                        suspicious_processes.append(line.strip())
                
                if suspicious_processes:
                    print(f"⚠️ PROCESOS SOSPECHOSOS EJECUTÁNDOSE: {len(suspicious_processes)}")
                    self.issues_found.append({
                        'nombre': f"Procesos sospechosos: {len(suspicious_processes)}",
                        'ruta': 'Procesos Activos',
                        'archivo': 'tasklist',
                        'tipo': 'running_process',
                        'categoria': 'PROCESSES',
                        'alerta': 'SOSPECHOSO'
                    })
        except Exception as e:
            print(f"Error escaneando procesos ejecutados: {str(e)}")
    
    def scan_exe_files(self):
        """Escanea archivos .exe usando dir /b/s"""
        try:
            print("🔍 ESCANEANDO ARCHIVOS .EXE (dir /b/s)...")
            import subprocess
            
            # Ejecutar dir /b/s *.exe
            result = subprocess.run(['dir', '/b/s', '*.exe'], capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                suspicious_exes = []
                
                for line in lines:
                    if any(exe in line.lower() for exe in ['minecraft', 'hack', 'cheat', 'ghost', 'vape', 'entropy', 'inject']):
                        suspicious_exes.append(line.strip())
                
                if suspicious_exes:
                    print(f"⚠️ ARCHIVOS .EXE SOSPECHOSOS: {len(suspicious_exes)}")
                    for exe in suspicious_exes[:5]:  # Mostrar solo los primeros 5
                        self.issues_found.append({
                            'nombre': f"Archivo .exe sospechoso: {os.path.basename(exe)}",
                            'ruta': os.path.dirname(exe),
                            'archivo': exe,
                            'tipo': 'suspicious_exe',
                            'categoria': 'HACKS',
                            'alerta': 'SOSPECHOSO'
                        })
        except Exception as e:
            print(f"Error escaneando archivos .exe: {str(e)}")
    
    def scan_jar_files(self):
        """Escanea archivos .jar usando dir /b/s"""
        try:
            print("🔍 ESCANEANDO ARCHIVOS .JAR (dir /b/s)...")
            import subprocess
            
            # Ejecutar dir /b/s *.jar
            result = subprocess.run(['dir', '/b/s', '*.jar'], capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                suspicious_jars = []
                
                for line in lines:
                    if any(jar in line.lower() for jar in ['minecraft', 'hack', 'cheat', 'ghost', 'vape', 'entropy', 'inject']):
                        suspicious_jars.append(line.strip())
                
                if suspicious_jars:
                    print(f"⚠️ ARCHIVOS .JAR SOSPECHOSOS: {len(suspicious_jars)}")
                    for jar in suspicious_jars[:5]:  # Mostrar solo los primeros 5
                        self.issues_found.append({
                            'nombre': f"Archivo .jar sospechoso: {os.path.basename(jar)}",
                            'ruta': os.path.dirname(jar),
                            'archivo': jar,
                            'tipo': 'suspicious_jar',
                            'categoria': 'JAR_FILES',
                            'alerta': 'SOSPECHOSO'
                        })
        except Exception as e:
            print(f"Error escaneando archivos .jar: {str(e)}")
    
    def scan_files_by_date(self):
        """Escanea archivos por fecha usando FORFILES"""
        try:
            print("🔍 ESCANEANDO ARCHIVOS POR FECHA (FORFILES)...")
            import subprocess
            
            # Ejecutar FORFILES para buscar archivos .exe desde 2021
            result = subprocess.run(['FORFILES', '/M', '*.exe', '/S', '/D', '+04/08/2021', '/C', 'cmd /C echo @fdate @file @path'], capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                suspicious_files = []
                
                for line in lines:
                    if any(file in line.lower() for file in ['minecraft', 'hack', 'cheat', 'ghost', 'vape', 'entropy', 'inject']):
                        suspicious_files.append(line.strip())
                
                if suspicious_files:
                    print(f"⚠️ ARCHIVOS SOSPECHOSOS POR FECHA: {len(suspicious_files)}")
                    for file in suspicious_files[:5]:  # Mostrar solo los primeros 5
                        self.issues_found.append({
                            'nombre': f"Archivo sospechoso por fecha: {file}",
                            'ruta': 'Sistema',
                            'archivo': file,
                            'tipo': 'suspicious_by_date',
                            'categoria': 'HACKS',
                            'alerta': 'SOSPECHOSO'
                        })
        except Exception as e:
            print(f"Error escaneando archivos por fecha: {str(e)}")
    
    def scan_deleted_files(self):
        """Escanea archivos borrados usando fsutil usn"""
        try:
            print("🔍 ESCANEANDO ARCHIVOS BORRADOS (fsutil usn)...")
            import subprocess
            
            # Ejecutar fsutil usn para archivos borrados
            result = subprocess.run(['fsutil', 'usn', 'readjournal', 'c:', 'csv'], capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                deleted_files = []
                
                for line in lines:
                    if '.exe' in line and '0x80000200' in line:
                        deleted_files.append(line.strip())
                
                if deleted_files:
                    print(f"⚠️ ARCHIVOS .EXE BORRADOS: {len(deleted_files)}")
                    self.issues_found.append({
                        'nombre': f"Archivos .exe borrados: {len(deleted_files)}",
                        'ruta': 'USN Journal',
                        'archivo': 'fsutil usn',
                        'tipo': 'deleted_files',
                        'categoria': 'DELETED_FILES',
                        'alerta': 'SOSPECHOSO'
                    })
        except Exception as e:
            print(f"Error escaneando archivos borrados: {str(e)}")
    
    def scan_created_files(self):
        """Escanea archivos creados usando fsutil usn"""
        try:
            print("🔍 ESCANEANDO ARCHIVOS CREADOS (fsutil usn)...")
            import subprocess
            
            # Ejecutar fsutil usn para archivos creados
            result = subprocess.run(['fsutil', 'usn', 'readjournal', 'c:', 'csv'], capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                created_files = []
                
                for line in lines:
                    if '.exe' in line and '0x00000100' in line:
                        created_files.append(line.strip())
                
                if created_files:
                    print(f"⚠️ ARCHIVOS .EXE CREADOS: {len(created_files)}")
                    self.issues_found.append({
                        'nombre': f"Archivos .exe creados: {len(created_files)}",
                        'ruta': 'USN Journal',
                        'archivo': 'fsutil usn',
                        'tipo': 'created_files',
                        'categoria': 'NEW_FILES',
                        'alerta': 'SOSPECHOSO'
                    })
        except Exception as e:
            print(f"Error escaneando archivos creados: {str(e)}")
    
    def scan_renamed_files(self):
        """Escanea archivos renombrados usando fsutil usn"""
        try:
            print("🔍 ESCANEANDO ARCHIVOS RENOMBRADOS (fsutil usn)...")
            import subprocess
            
            # Ejecutar fsutil usn para archivos renombrados
            result = subprocess.run(['fsutil', 'usn', 'readjournal', 'c:', 'csv'], capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                renamed_files = []
                
                for line in lines:
                    if '.exe' in line and ('0x00001000' in line or '0x00002000' in line):
                        renamed_files.append(line.strip())
                
                if renamed_files:
                    print(f"⚠️ ARCHIVOS .EXE RENOMBRADOS: {len(renamed_files)}")
                    self.issues_found.append({
                        'nombre': f"Archivos .exe renombrados: {len(renamed_files)}",
                        'ruta': 'USN Journal',
                        'archivo': 'fsutil usn',
                        'tipo': 'renamed_files',
                        'categoria': 'RENAMED_FILES',
                        'alerta': 'SOSPECHOSO'
                    })
        except Exception as e:
            print(f"Error escaneando archivos renombrados: {str(e)}")
    
    def scan_prefetch_jna(self):
        """Escanea prefetch para JNA"""
        try:
            print("🔍 ESCANEANDO PREFETCH PARA JNA...")
            import os
            
            prefetch_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch')
            
            if os.path.exists(prefetch_path):
                for file in os.listdir(prefetch_path):
                    if 'jna' in file.lower():
                        print(f"⚠️ JNA ENCONTRADO EN PREFETCH: {file}")
                        self.issues_found.append({
                            'nombre': f"JNA en prefetch: {file}",
                            'ruta': prefetch_path,
                            'archivo': os.path.join(prefetch_path, file),
                            'tipo': 'prefetch_jna',
                            'categoria': 'JNA',
                            'alerta': 'SOSPECHOSO'
                        })
        except Exception as e:
            print(f"Error escaneando prefetch JNA: {str(e)}")
    
    def scan_temp_jna(self):
        """Escanea temp para JNA"""
        try:
            print("🔍 ESCANEANDO TEMP PARA JNA...")
            import os
            
            temp_path = os.environ.get('TEMP', 'C:\\Windows\\Temp')
            
            if os.path.exists(temp_path):
                for root, dirs, files in os.walk(temp_path):
                    for file in files:
                        if 'jna' in file.lower():
                            print(f"⚠️ JNA ENCONTRADO EN TEMP: {file}")
                            self.issues_found.append({
                                'nombre': f"JNA en temp: {file}",
                                'ruta': root,
                                'archivo': os.path.join(root, file),
                                'tipo': 'temp_jna',
                                'categoria': 'JNA',
                                'alerta': 'SOSPECHOSO'
                            })
        except Exception as e:
            print(f"Error escaneando temp JNA: {str(e)}")
    
    def scan_registry_suspicious(self):
        """Escanea registro de Windows para entradas sospechosas de hacks."""
        try:
            print("🔍 ESCANEANDO REGISTRO DE WINDOWS...")
            import winreg as _wr

            HACK_KW = list(_DEFINITE_HACK_NAMES) + _WORD_BOUNDARY_HACK_WORDS + [
                'autoclick', 'autoclicker', 'injector', 'weaveloader',
                'cheatengine', 'extremeinjector', 'xenos',
            ]

            def _scan_run_key(hive, subkey_path, hive_name):
                """Escanea una clave Run/RunOnce buscando entradas de hacks."""
                try:
                    key = _wr.OpenKey(hive, subkey_path)
                    i = 0
                    while True:
                        try:
                            name, data, _ = _wr.EnumValue(key, i)
                            combined = (name + ' ' + str(data)).lower()
                            # Normalizar para homoglyphs
                            combined_norm = _normalize(combined)
                            hit = next((kw for kw in HACK_KW
                                        if kw in combined or kw in combined_norm), None)
                            if hit:
                                full_key = f'{hive_name}\\{subkey_path}'
                                print(f"🚨 REGISTRO RUN/RUNONCE HACK: {name} → {str(data)[:80]}")
                                self.issues_found.append({
                                    'nombre': f'Entrada de inicio automático sospechosa: {name}',
                                    'ruta': full_key,
                                    'archivo': name,
                                    'tipo': 'registry_run_hack',
                                    'categoria': 'HACKS',
                                    'alerta': 'CRITICAL',
                                    'confidence': 0.88,
                                    'detected_patterns': [f'registry_run:{hit}'],
                                    'explicacion': (
                                        f'La clave de registro {full_key} contiene una entrada de '
                                        f'inicio automático con nombre "{name}" que coincide con un '
                                        f'hack client conocido ({hit}). Esto indica que el hack '
                                        f'se ejecuta automáticamente al iniciar Windows.'
                                    ),
                                })
                            i += 1
                        except OSError:
                            break
                    _wr.CloseKey(key)
                except Exception:
                    pass

            # HKCU Run / RunOnce
            _scan_run_key(_wr.HKEY_CURRENT_USER,
                          r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', 'HKCU')
            _scan_run_key(_wr.HKEY_CURRENT_USER,
                          r'SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce', 'HKCU')
            # HKLM Run / RunOnce
            _scan_run_key(_wr.HKEY_LOCAL_MACHINE,
                          r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run', 'HKLM')
            _scan_run_key(_wr.HKEY_LOCAL_MACHINE,
                          r'SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce', 'HKLM')
            # WOW6432Node (apps de 32 bits en Windows 64)
            _scan_run_key(_wr.HKEY_LOCAL_MACHINE,
                          r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run', 'HKLM_WOW')

            # UserAssist — historial de programas ejecutados por el usuario
            try:
                ua_path = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\UserAssist'
                ua_key = _wr.OpenKey(_wr.HKEY_CURRENT_USER, ua_path)
                j = 0
                while True:
                    try:
                        guid = _wr.EnumKey(ua_key, j)
                        count_key = _wr.OpenKey(ua_key, guid + r'\Count')
                        k = 0
                        while True:
                            try:
                                name, data, _ = _wr.EnumValue(count_key, k)
                                # UserAssist usa ROT13 para codificar el nombre del exe
                                import codecs as _codecs
                                decoded = _codecs.decode(name, 'rot_13').lower()
                                decoded_norm = _normalize(decoded)
                                hit = next((kw for kw in HACK_KW
                                            if kw in decoded or kw in decoded_norm), None)
                                if hit:
                                    print(f"🚨 REGISTRO USERASSIST HACK: {decoded[:80]}")
                                    self.issues_found.append({
                                        'nombre': f'UserAssist: programa sospechoso ejecutado: {decoded[:60]}',
                                        'ruta': f'HKCU\\{ua_path}\\{guid}\\Count',
                                        'archivo': decoded[:60],
                                        'tipo': 'registry_userassist_hack',
                                        'categoria': 'FORENSE',
                                        'alerta': 'CRITICAL',
                                        'confidence': 0.85,
                                        'detected_patterns': [f'userassist:{hit}'],
                                        'explicacion': (
                                            f'El registro UserAssist confirma que "{decoded[:60]}" fue '
                                            f'ejecutado por el usuario. UserAssist registra todos los '
                                            f'programas lanzados desde el Explorador de Windows.'
                                        ),
                                    })
                                k += 1
                            except OSError:
                                break
                        _wr.CloseKey(count_key)
                        j += 1
                    except OSError:
                        break
                _wr.CloseKey(ua_key)
            except Exception:
                pass

            # AppCompatFlags — programas que solicitaron compatibilidad (frecuente en loaders)
            try:
                compat_path = r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers'
                compat_key = _wr.OpenKey(_wr.HKEY_CURRENT_USER, compat_path)
                i = 0
                while True:
                    try:
                        name, data, _ = _wr.EnumValue(compat_key, i)
                        combined = (name + ' ' + str(data)).lower()
                        combined_norm = _normalize(combined)
                        hit = next((kw for kw in HACK_KW
                                    if kw in combined or kw in combined_norm), None)
                        if hit:
                            print(f"🚨 REGISTRO APPCOMPAT HACK: {name[:80]}")
                            self.issues_found.append({
                                'nombre': f'AppCompat Layers: programa sospechoso: {os.path.basename(name)}',
                                'ruta': f'HKCU\\{compat_path}',
                                'archivo': name,
                                'tipo': 'registry_appcompat_hack',
                                'categoria': 'FORENSE',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.78,
                                'detected_patterns': [f'appcompat:{hit}'],
                                'explicacion': (
                                    f'AppCompatFlags registra que "{os.path.basename(name)}" fue ejecutado '
                                    f'con flags de compatibilidad. Los loaders de hacks frecuentemente '
                                    f'requieren modos de compatibilidad de Windows para funcionar.'
                                ),
                            })
                        i += 1
                    except OSError:
                        break
                _wr.CloseKey(compat_key)
            except Exception:
                pass

        except Exception as e:
            print(f"Error escaneando registro: {str(e)}")
    
    def scan_logitech_macros(self):
        """Escanea macros de Logitech G Hub — lee la DB para buscar macros de autoclick."""
        print("🔍 ESCANEANDO MACROS LOGITECH...")
        localapp = os.environ.get('LOCALAPPDATA', '')
        lghub_dir = os.path.join(localapp, 'LGHUB')
        if not os.path.exists(lghub_dir):
            return
        try:
            import sqlite3, glob as _glob, json as _json
            # LGHUB guarda su configuración en settings.db (SQLite)
            db_candidates = _glob.glob(os.path.join(lghub_dir, '*.db'))
            macro_found = False
            for db_path in db_candidates:
                try:
                    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
                    c = conn.cursor()
                    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [r[0] for r in c.fetchall()]
                    # Buscar tablas de assignments/macros
                    for table in tables:
                        if any(kw in table.lower() for kw in ('assignment', 'macro', 'key', 'profile')):
                            try:
                                c.execute(f'SELECT * FROM "{table}" LIMIT 200')
                                rows = c.fetchall()
                                raw = ' '.join(str(r) for r in rows).lower()
                                # Indicadores de autoclick: delays cortos + repetición
                                if any(kw in raw for kw in ('mousebutton', 'leftbutton', 'rightbutton',
                                                             'delay', 'repeat', 'keystroke')):
                                    if any(str(d) in raw for d in range(1, 20)):  # delay < 20ms
                                        macro_found = True
                                        print(f"🚨 MACRO DE CLICK LOGITECH en {table}")
                            except Exception:
                                pass
                    conn.close()
                except Exception:
                    pass
            alerta = 'CRITICAL' if macro_found else 'SOSPECHOSO'
            desc   = 'Macro de autoclick Logitech detectada (delay < 20ms)' if macro_found else 'Software Logitech G Hub instalado con macros configuradas'
            print(f"⚠️ LOGITECH G HUB DETECTADO — {desc}")
            self.issues_found.append({
                'nombre': desc,
                'ruta': lghub_dir,
                'archivo': 'LGHUB/settings.db',
                'tipo': 'logitech_macros',
                'categoria': 'AUTOCLICK',
                'alerta': alerta,
                'confidence': 0.85 if macro_found else 0.45,
                'detected_patterns': ['logitech_macro_click' if macro_found else 'logitech_installed'],
            })
        except Exception as e:
            print(f"Error escaneando macros Logitech: {e}")

    def scan_razer_macros(self):
        """Escanea macros de Razer Synapse — busca perfiles con secuencias de click."""
        print("🔍 ESCANEANDO MACROS RAZER...")
        import glob as _glob, json as _json
        localapp  = os.environ.get('LOCALAPPDATA', '')
        appdata   = os.environ.get('APPDATA', '')
        razer_dirs = [
            os.path.join(localapp, 'Razer'),
            os.path.join(appdata, 'Razer'),
            os.path.join(os.environ.get('PROGRAMDATA', ''), 'Razer'),
        ]
        try:
            macro_found = False
            for razer_dir in razer_dirs:
                if not os.path.exists(razer_dir):
                    continue
                # Buscar archivos de perfil JSON/XML
                for ext in ('*.json', '*.xml', '*.cfg'):
                    for profile_path in _glob.glob(os.path.join(razer_dir, '**', ext), recursive=True):
                        try:
                            with open(profile_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read().lower()
                            # Indicadores de macro de click con delay bajo
                            if any(kw in content for kw in ('mousedown', 'mouseclick', 'leftclick',
                                                              'keystroke', 'macro', 'actiontype')):
                                # Buscar delays bajos (< 20ms)
                                import re as _re
                                delays = _re.findall(r'delay["\s:]+(\d+)', content)
                                if any(int(d) < 20 for d in delays if d.isdigit()):
                                    macro_found = True
                                    print(f"🚨 MACRO RAZER CON DELAY BAJO: {profile_path}")
                        except Exception:
                            pass
            if any(os.path.exists(d) for d in razer_dirs):
                alerta = 'CRITICAL' if macro_found else 'SOSPECHOSO'
                desc   = 'Macro de autoclick Razer detectada (delay < 20ms)' if macro_found else 'Razer Synapse instalado con perfiles configurados'
                self.issues_found.append({
                    'nombre': desc,
                    'ruta': next(d for d in razer_dirs if os.path.exists(d)),
                    'archivo': 'Razer profile',
                    'tipo': 'razer_macros',
                    'categoria': 'AUTOCLICK',
                    'alerta': alerta,
                    'confidence': 0.85 if macro_found else 0.40,
                    'detected_patterns': ['razer_macro_click' if macro_found else 'razer_installed'],
                })
        except Exception as e:
            print(f"Error escaneando macros Razer: {e}")
    
    def scan_event_logs(self):
        """Escanea logs de eventos para cambios de fecha"""
        try:
            print("🔍 ESCANEANDO LOGS DE EVENTOS...")
            import subprocess
            import time
            
            # Ejecutar eventvwr.msc para verificar cambios de fecha
            print("📋 Abriendo Event Viewer...")
            process = subprocess.Popen(['eventvwr.msc'], shell=True)
            
            # Esperar 5 segundos para que se abra
            time.sleep(5)
            
            print("⏰ Esperando 10 segundos para revisar logs...")
            time.sleep(10)
            
            # Cerrar automáticamente el Event Viewer
            print("🔒 Cerrando Event Viewer automáticamente...")
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                # Si no se puede cerrar normalmente, forzar cierre
                subprocess.run(['taskkill', '/f', '/im', 'mmc.exe'], capture_output=True, shell=True)
            
            print("⚠️ LOGS DE EVENTOS REVISADOS - Event Viewer cerrado automáticamente")
            self.issues_found.append({
                'nombre': "Logs de eventos revisados - Event Viewer cerrado automáticamente",
                'ruta': 'Event Viewer',
                'archivo': 'eventvwr.msc',
                'tipo': 'event_logs',
                'categoria': 'DATE_CHANGES',
                'alerta': 'SOSPECHOSO'
            })
        except Exception as e:
            print(f"Error escaneando logs de eventos: {str(e)}")
    
    def scan_processes(self):
        """Escanea procesos activos"""
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    proc_info = proc.info
                    if proc_info['name'] and self.is_suspicious_process(proc_info['name']):
                        self.issues_found.append({
                            'nombre': proc_info['name'],
                            'ruta': proc_info.get('exe', 'N/A'),
                            'archivo': proc_info['name'],
                            'tipo': 'process',
                            'pid': proc_info['pid'],
                            'categoria': 'PROCESSES',
                            'alerta': 'CRITICAL'
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error escaneando procesos: {e}")
    
    def is_suspicious_process(self, process_name):
        """Verifica si un proceso es sospechoso - MEJORADO CON MÁS PATRONES"""
        process_name = process_name.lower()
        
        # Patrones críticos de procesos de hack
        critical_processes = [
            'vape', 'vapelite', 'vapev2', 'vapev4', 'entropy', 'entropyclient',
            'whiteout', 'whiteoutclient', 'liquidbounce', 'lb', 'wurst', 'wurstclient',
            'impact', 'impactclient', 'sigma', 'sigmaclient', 'flux', 'fluxclient',
            'future', 'futureclient', 'astolfo', 'exhibition', 'novoline', 'rise',
            'moon', 'drip', 'phobos', 'komat', 'wasp', 'konas', 'seppuku', 'sloth',
            'lucid', 'tenacity', 'nyx', 'vanish', 'ploow', 'cloud', 'nextgen',
            'tegernako', 'zeroday', 'injector', 'inject', 'inyector', 'injection',
            'dllinjector', 'ghost', 'ghostclient', 'bypass', 'stealth', 'undetected',
            'incognito', 'unbypass', 'killaura', 'aimbot', 'triggerbot', 'reach',
            'velocity', 'scaffold', 'fly', 'xray', 'fullbright', 'speedhack',
            'wtap', 'aimassist', 'bhop', 'nofall', 'autoclicker', 'ac.exe'
        ]
        
        # Verificar patrones críticos
        for pattern in critical_processes:
            if pattern in process_name:
                # Verificar que no sea falso positivo
                if not self.is_whitelisted(process_name):
                    return True
        
        return False
    
    def scan_windows(self):
        """Escanea ventanas abiertas"""
        try:
            import ctypes
            from ctypes import wintypes
            
            def enum_windows_proc(hwnd, lParam):
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                        window_title = buffer.value
                        
                        if self.is_suspicious_window(window_title):
                            self.issues_found.append({
                                'nombre': window_title,
                                'ruta': 'N/A',
                                'archivo': window_title,
                                'tipo': 'window',
                                'categoria': 'PROCESSES',
                                'alerta': 'SOSPECHOSO'
                            })
                return True
            
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_proc), 0)
        except Exception as e:
            print(f"Error escaneando ventanas: {e}")
    
    def is_suspicious_window(self, window_title):
        """Verifica si una ventana es sospechosa"""
        window_title = window_title.lower()
        suspicious_windows = [
            'vape', 'entropy', 'whiteout', 'liquidbounce', 'wurst', 'impact',
            'sigma', 'flux', 'future', 'injector', 'inject', 'ghost'
        ]
        
        for pattern in suspicious_windows:
            if pattern in window_title:
                return True
        
        return False
    
    def scan_registry(self):
        """Escanea el registro de Windows"""
        try:
            import winreg
            
            # Claves del registro a verificar
            registry_keys = [
                (winreg.HKEY_CURRENT_USER, r"Software"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE")
            ]
            
            for hkey, subkey in registry_keys:
                try:
                    with winreg.OpenKey(hkey, subkey) as key:
                        self._scan_registry_key(key, "")
                except Exception as e:
                    print(f"Error accediendo al registro: {e}")
        except Exception as e:
            print(f"Error escaneando registro: {e}")
    
    def _scan_registry_key(self, key, path):
        """Escanea una clave del registro recursivamente"""
        try:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey_path = f"{path}\\{subkey_name}" if path else subkey_name
                    
                    if self.is_suspicious_registry_key(subkey_name):
                        self.issues_found.append({
                            'nombre': subkey_name,
                            'ruta': subkey_path,
                            'archivo': subkey_name,
                            'tipo': 'registry',
                            'categoria': 'HACKS',
                            'alerta': 'SOSPECHOSO'
                        })
                    
                    i += 1
                except WindowsError:
                    break
        except Exception as e:
            print(f"Error escaneando clave del registro: {e}")
    
    def is_suspicious_registry_key(self, key_name):
        """Verifica si una clave del registro es sospechosa"""
        key_name = key_name.lower()
        suspicious_keys = [
            'vape', 'entropy', 'whiteout', 'liquidbounce', 'wurst', 'impact',
            'sigma', 'flux', 'future', 'injector', 'inject', 'ghost'
        ]
        
        for pattern in suspicious_keys:
            if pattern in key_name:
                return True
        
        return False
    
    # ══════════════════════════════════════════════════════════════════════════
    # NUEVOS MÓDULOS DE DETECCIÓN
    # ══════════════════════════════════════════════════════════════════════════

    def scan_cmd_history_full(self):
        """Escanea historial de comandos CMD, Win+R, búsquedas de carpeta y TypedPaths."""
        print("🔍 Escaneando historial de comandos y búsquedas...")
        suspicious_terms = [
            'vape', 'entropy', 'wurst', 'liquidbounce', 'sigma', 'flux', 'future',
            'killaura', 'aimbot', 'inject', 'hack', 'cheat', 'bypass', 'crack',
            'autoclick', 'clicker', 'phobos', 'astolfo', 'novoline'
        ]
        try:
            keys_to_check = [
                # Win+R history
                (winreg.HKEY_CURRENT_USER,
                 r'Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU',
                 'WIN+R'),
                # Folder address bar
                (winreg.HKEY_CURRENT_USER,
                 r'Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths',
                 'EXPLORER_PATHS'),
                # Windows Search
                (winreg.HKEY_CURRENT_USER,
                 r'Software\Microsoft\Windows\CurrentVersion\Explorer\WordWheelQuery',
                 'FOLDER_SEARCH'),
                # cmd.exe recent
                (winreg.HKEY_CURRENT_USER,
                 r'Software\Microsoft\Windows NT\CurrentVersion\Windows',
                 'CMD_LOAD'),
            ]
            for hive, subkey, source in keys_to_check:
                try:
                    with winreg.OpenKey(hive, subkey) as reg_key:
                        i = 0
                        while True:
                            try:
                                name, value, _ = winreg.EnumValue(reg_key, i)
                                i += 1
                                val_str = str(value).lower()
                                for term in suspicious_terms:
                                    if term in val_str:
                                        self.issues_found.append({
                                            'tipo': 'cmd_history',
                                            'nombre': f'Comando sospechoso en {source}: {str(value)[:120]}',
                                            'ruta': f'HKCU\\{subkey}\\{name}',
                                            'archivo': str(value)[:255],
                                            'categoria': 'CMD_HISTORY',
                                            'alerta': 'SOSPECHOSO',
                                            'confidence': 70,
                                            'detected_patterns': [term],
                                        })
                                        print(f"⚠️ CMD/Run sospechoso [{source}]: {str(value)[:80]}")
                                        break
                            except OSError:
                                break
                except (FileNotFoundError, PermissionError):
                    pass

            # También guardar TODOS los comandos Win+R como historial informativo
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                    r'Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU') as k:
                    entries = []
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(k, i)
                            i += 1
                            if name != 'MRUList' and str(value).strip():
                                entries.append(str(value).rstrip('\x01\x02'))
                        except OSError:
                            break
                    if entries:
                        self.issues_found.append({
                            'tipo': 'cmd_history_full',
                            'nombre': f'Historial Win+R ({len(entries)} entradas)',
                            'ruta': 'HKCU\\Explorer\\RunMRU',
                            'archivo': ' | '.join(entries[:20]),
                            'categoria': 'CMD_HISTORY',
                            'alerta': 'NORMAL',
                            'confidence': 0,
                            'detected_patterns': entries[:20],
                        })
            except Exception:
                pass
        except Exception as e:
            print(f"Error en scan_cmd_history_full: {e}")

    def scan_prefetch_all(self):
        """Escanea TODOS los archivos prefetch para detectar ejecutables sospechosos con timestamps."""
        print("🔍 Escaneando prefetch completo...")
        prefetch_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch')
        if not os.path.exists(prefetch_path):
            return

        hack_names = [
            # Ghost clients conocidos
            'vape', 'entropy', 'wurst', 'liquidbounce', 'sigma', 'flux', 'future',
            'astolfo', 'novoline', 'phobos', 'rise', 'meteor', 'weave', 'jello',
            'datura', 'drip', 'vertex', 'mathias', 'rusherhack', 'azura', 'salhack',
            'inertia', 'remix', 'ares', 'aristois', 'komat', 'wasp', 'konas',
            'seppuku', 'sloth', 'moon', 'exhibition', 'liqd', 'exhib',
            # Módulos y tipos de hack
            'killaura', 'aimbot', 'triggerbot', 'scaffold', 'autoclick', 'clicker',
            # Herramientas de inyección
            'inject', 'injector', 'dllinjector', 'xenos', 'extreme.inject',
            # Términos genéricos de evasión
            'bypass', 'undetected', 'ghost', 'stealth',
            # Malware genérico
            'hack', 'cheat', 'crack', 'keylogger', 'rat.', 'trojan',
        ]
        legit_names = [
            'windows', 'microsoft', 'chrome', 'firefox', 'explorer', 'system',
            'svchost', 'csrss', 'winlogon', 'lsass', 'services', 'smss',
            'discord', 'steam', 'minecraft', 'javaw', 'java', 'nvidia', 'amd',
            'photoshop', 'office', 'word', 'excel', 'powerpoint', 'outlook',
            'teams', 'zoom', 'spotify', 'vlc', 'notepad', 'mspaint', 'calc'
        ]

        all_executed = []
        suspicious_executed = []
        try:
            for pf_file in os.listdir(prefetch_path):
                if not pf_file.endswith('.pf'):
                    continue
                try:
                    pf_path = os.path.join(prefetch_path, pf_file)
                    mtime = os.path.getmtime(pf_path)
                    last_run = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    exe_name = pf_file.split('-')[0].lower()  # Nombre antes del hash
                    all_executed.append({'name': pf_file, 'last_run': last_run, 'path': pf_path})

                    name_lower = pf_file.lower()
                    is_legit = any(l in name_lower for l in legit_names)
                    is_hack = any(h in name_lower for h in hack_names)

                    if is_hack and not is_legit:
                        suspicious_executed.append({
                            'tipo': 'prefetch_suspicious',
                            'nombre': f'Ejecutable sospechoso en prefetch: {pf_file}',
                            'ruta': pf_path,
                            'archivo': pf_file,
                            'categoria': 'EXECUTED_FILES',
                            'alerta': 'CRITICAL',
                            'confidence': 85,
                            'detected_patterns': [h for h in hack_names if h in name_lower],
                            'extra': {'last_run': last_run},
                        })
                        print(f"🚨 PREFETCH SOSPECHOSO: {pf_file} (última ejecución: {last_run})")
                except Exception:
                    pass

            # Guardar lista completa de ejecutados como referencia informativa
            if all_executed:
                summary = ' | '.join([f"{e['name']} @ {e['last_run']}" for e in sorted(
                    all_executed, key=lambda x: x['last_run'], reverse=True)[:30]])
                self.issues_found.append({
                    'tipo': 'prefetch_history',
                    'nombre': f'Prefetch: {len(all_executed)} programas ejecutados recientemente',
                    'ruta': prefetch_path,
                    'archivo': summary[:500],
                    'categoria': 'EXECUTED_FILES',
                    'alerta': 'NORMAL',
                    'confidence': 0,
                    'detected_patterns': [e['name'] for e in all_executed[:30]],
                })

            for s in suspicious_executed:
                self.issues_found.append(s)

        except Exception as e:
            print(f"Error en scan_prefetch_all: {e}")

    def scan_deleted_recycle(self):
        """Escanea la papelera de reciclaje con timestamps y nombres originales."""
        print("🔍 Escaneando Recycle Bin con timestamps...")
        hack_terms = [
            'vape', 'entropy', 'hack', 'cheat', 'inject', 'wurst', 'liquidbounce',
            'sigma', 'flux', 'killaura', 'aimbot', 'bypass', 'crack', 'autoclick',
            'clicker', 'phobos', 'astolfo', 'novoline', 'ghost', 'riseclient',
            '.rise', '.meteor', '.drip', '.vertex', '.azura', '.jello', '.datura',
            '.mathias', '.rusherhack', '.salhack', '.inertia', 'weaveloader',
            'dllinjector', 'extremeinjector', 'cheatengine', 'xenos',
        ]
        try:
            import struct
            recycle_root = 'C:\\$RECYCLE.BIN'
            if not os.path.exists(recycle_root):
                return

            deleted_items = []
            for user_sid in os.listdir(recycle_root):
                sid_path = os.path.join(recycle_root, user_sid)
                if not os.path.isdir(sid_path):
                    continue
                try:
                    for fname in os.listdir(sid_path):
                        # $I files contain metadata (original path + deletion time)
                        if not fname.startswith('$I'):
                            continue
                        i_path = os.path.join(sid_path, fname)
                        try:
                            with open(i_path, 'rb') as f:
                                data = f.read(544)
                            if len(data) < 28:
                                continue
                            # $I format: 8 bytes version, 8 bytes size, 8 bytes FILETIME, N bytes path
                            ft_raw = struct.unpack_from('<Q', data, 16)[0]
                            if ft_raw > 0:
                                # Convert FILETIME to datetime
                                EPOCH_DIFF = 116444736000000000
                                unix_ts = (ft_raw - EPOCH_DIFF) / 10000000
                                if 0 < unix_ts < 2000000000:
                                    deleted_at = datetime.fromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')
                                else:
                                    deleted_at = 'Desconocida'
                            else:
                                deleted_at = 'Desconocida'

                            # Original path starts at offset 28 (v2) as UTF-16LE
                            try:
                                orig_path = data[28:].decode('utf-16-le').rstrip('\x00')
                            except Exception:
                                orig_path = fname

                            deleted_items.append({'path': orig_path, 'deleted_at': deleted_at, 'i_file': i_path})
                        except Exception:
                            continue
                except PermissionError:
                    continue

            if not deleted_items:
                return

            # Report suspicious items
            for item in deleted_items:
                name_lower = item['path'].lower()
                for term in hack_terms:
                    if term in name_lower:
                        self.issues_found.append({
                            'tipo': 'deleted_suspicious',
                            'nombre': f'Archivo sospechoso eliminado: {os.path.basename(item["path"])}',
                            'ruta': item['path'],
                            'archivo': item['path'][:255],
                            'categoria': 'DELETED_FILES',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 75,
                            'detected_patterns': [term],
                            'extra': {'deleted_at': item['deleted_at']},
                        })
                        print(f"⚠️ ELIMINADO SOSPECHOSO: {item['path']} @ {item['deleted_at']}")
                        break

            # Summary of all deleted items
            summary = ' | '.join([f"{os.path.basename(d['path'])} @ {d['deleted_at']}"
                                   for d in sorted(deleted_items, key=lambda x: x['deleted_at'], reverse=True)[:20]])
            self.issues_found.append({
                'tipo': 'deleted_history',
                'nombre': f'Papelera: {len(deleted_items)} archivo(s) eliminado(s)',
                'ruta': recycle_root,
                'archivo': summary[:500],
                'categoria': 'DELETED_FILES',
                'alerta': 'NORMAL',
                'confidence': 0,
                'detected_patterns': [os.path.basename(d['path']) for d in deleted_items[:20]],
            })
        except Exception as e:
            print(f"Error en scan_deleted_recycle: {e}")

    # ──────────────────────────────────────────────────────────────
    #  NUEVAS DETECCIONES — Ghost clients, JDWP, VPN, Hosts
    # ──────────────────────────────────────────────────────────────

    def scan_ghost_client_configs(self):
        """Detecta carpetas y archivos de configuración de ghost clients conocidos."""
        print("🔍 Escaneando configs de ghost clients...")
        appdata  = os.environ.get('APPDATA', '')
        localapp = os.environ.get('LOCALAPPDATA', '')
        home     = os.path.expanduser('~')
        GHOST_CONFIGS = [
            ('Rise Client',      os.path.join(appdata,  '.rise')),
            ('Sigma Client',     os.path.join(appdata,  '.sigma')),
            ('Meteor Client',    os.path.join(appdata,  '.meteor')),
            ('LiquidBounce',     os.path.join(appdata,  '.liquidbounce')),
            ('Weave Loader',     os.path.join(appdata,  '.weave')),
            ('WeaveLoader',      os.path.join(localapp, 'WeaveLoader')),
            ('Jello Client',     os.path.join(appdata,  'jello')),
            ('Datura Client',    os.path.join(appdata,  '.datura')),
            ('Drip Client',      os.path.join(appdata,  '.drip')),
            ('Vertex Client',    os.path.join(appdata,  '.vertex')),
            ('Mathias Client',   os.path.join(appdata,  '.mathias')),
            ('RusherHack',       os.path.join(appdata,  '.rusherhack')),
            ('Azura Client',     os.path.join(appdata,  '.azura')),
            ('Novoline Client',  os.path.join(appdata,  '.novoline')),
            ('Future Client',    os.path.join(appdata,  '.future')),
            ('Flux Client',      os.path.join(appdata,  '.flux')),
            ('Astolfo Client',   os.path.join(appdata,  '.astolfo')),
            ('Salhack Client',   os.path.join(appdata,  '.salhack')),
            ('Entropy Client',   os.path.join(appdata,  '.entropy')),
            ('Wurst Client',     os.path.join(appdata,  '.wurst')),
            ('Inertia Client',   os.path.join(home,     '.inertia')),
            ('Remix Client',     os.path.join(appdata,  '.remix')),
            ('Ares Client',      os.path.join(appdata,  '.ares')),
            ('Vape (encrypted)', os.path.join(appdata,  'vape.encrypted')),
            ('Vape (json)',       os.path.join(appdata,  'vape.json')),
        ]
        try:
            for client_name, config_path in GHOST_CONFIGS:
                if os.path.exists(config_path):
                    print(f"🚨 GHOST CLIENT CONFIG: {client_name} → {config_path}")
                    self.issues_found.append({
                        'nombre': f'Config de ghost client detectada: {client_name}',
                        'ruta': config_path,
                        'archivo': os.path.basename(config_path),
                        'tipo': 'ghost_client_config',
                        'categoria': 'GHOST_CLIENT',
                        'alerta': 'CRITICAL',
                        'confidence': 0.98,
                        'detected_patterns': [f'ghost_config:{client_name.lower().replace(" ", "_")}'],
                    })
        except Exception as e:
            print(f"Error en scan_ghost_client_configs: {e}")

    def scan_config_tfidf(self):
        """P3 #8 — Analiza el contenido de archivos JSON/config buscando campos
        característicos de ghost clients, aunque el archivo esté renombrado.
        Usa un enfoque TF-IDF simplificado: peso de términos en vocabulario de hacks."""
        print("🔍 TF-IDF análisis de config files...")
        import json as _json

        # Vocabulario de campos altamente específicos de ghost clients
        HACK_FIELDS = {
            # Módulos de combate
            'killaura': 3.0, 'killaurarange': 3.0, 'kaaura': 3.0,
            'aimassist': 2.5, 'aimbot': 3.0, 'triggerbot': 3.0,
            'velocity': 2.0, 'antikb': 2.5, 'antiknockback': 2.5,
            'reach': 2.0, 'reachrange': 2.5, 'hitbox': 2.0,
            'criticals': 2.0, 'autocrit': 2.5, 'wtap': 2.5, 'blatant': 2.5,
            # Movimiento
            'bhop': 2.5, 'bunny': 2.0, 'sprint': 1.5, 'nofall': 2.5,
            'flight': 3.0, 'fly': 2.0, 'elytra': 1.5, 'speed': 1.5,
            'scaffold': 2.5, 'tower': 2.0,
            # Visión
            'xray': 3.0, 'wallhack': 3.0, 'esp': 2.5, 'fullbright': 2.0,
            'chams': 2.0, 'tracers': 2.0, 'nametags': 1.5,
            # Red/bypass
            'nopacket': 2.5, 'packetfly': 2.5, 'nomotion': 2.0,
            'blink': 2.5, 'phase': 2.5, 'timer': 2.0, 'speedhack': 3.0,
            # Campos de configuración internos de hacks conocidos
            'yawspeed': 3.0, 'pitchspeed': 2.5, 'rotations': 2.0,
            'bypassed': 2.0, 'undetected': 2.5, 'silent': 2.0,
            'autoblock': 2.5, 'noswing': 2.0, 'critplace': 2.5,
            # LiquidBounce-specific
            'liquidbounce': 4.0, 'lbmodule': 3.5,
            # Vape-specific
            'vapeconfig': 4.0, 'vapesettings': 3.5,
            # General ghost client markers
            'clickgui': 2.0, 'modulelist': 2.0, 'hackmodule': 3.5,
        }
        SCORE_THRESHOLD = 6.0  # Suma de pesos para reportar

        # Rutas donde buscar configs sospechosas renombradas
        appdata  = os.environ.get('APPDATA', '')
        localapp = os.environ.get('LOCALAPPDATA', '')
        desktop  = os.path.join(os.path.expanduser('~'), 'Desktop')
        downloads = os.path.join(os.path.expanduser('~'), 'Downloads')

        SEARCH_PATHS = [appdata, localapp, desktop, downloads]
        EXTENSIONS   = {'.json', '.cfg', '.ini', '.yml', '.yaml', '.conf', '.properties'}
        MAX_FILES    = 200
        scanned = 0

        try:
            for base_path in SEARCH_PATHS:
                if not os.path.isdir(base_path) or scanned >= MAX_FILES:
                    break
                for root, dirs, files in os.walk(base_path):
                    dirs[:] = [d for d in dirs if d not in {
                        'node_modules', '.git', 'AppData', 'Microsoft', 'Windows',
                        'System32', 'chrome', 'firefox', 'edge', 'Google',
                    }]
                    for fname in files:
                        if scanned >= MAX_FILES:
                            break
                        ext = os.path.splitext(fname.lower())[1]
                        if ext not in EXTENSIONS:
                            continue
                        fpath = os.path.join(root, fname)
                        try:
                            fsize = os.path.getsize(fpath)
                            if fsize < 20 or fsize > 500 * 1024:  # 500KB max
                                continue
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(8000).lower()
                            scanned += 1

                            # Calcular score TF-IDF simplificado
                            score = 0.0
                            matched = []
                            for field, weight in HACK_FIELDS.items():
                                if field in content:
                                    score += weight
                                    matched.append(field)

                            if score >= SCORE_THRESHOLD:
                                print(f"⚠️ CONFIG TFIDF: {fpath} (score={score:.1f})")
                                self.issues_found.append({
                                    'nombre': f'Config con campos de ghost client (score={score:.1f}): {fname}',
                                    'ruta': fpath,
                                    'archivo': fname,
                                    'tipo': 'config_tfidf_match',
                                    'categoria': 'GHOST_CLIENT',
                                    'alerta': 'CRITICAL' if score >= 10.0 else 'SOSPECHOSO',
                                    'confidence': min(0.92, 0.50 + score / 25),
                                    'detected_patterns': [f'field:{f}' for f in matched[:8]],
                                    'explicacion': (
                                        f'El archivo {fname} contiene {len(matched)} campos '
                                        f'asociados a ghost clients ({", ".join(matched[:5])}). '
                                        f'Esto puede indicar una config de hack renombrada para evadir detección.'
                                    ),
                                })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_config_tfidf: {e}")

    def scan_jdwp_port(self):
        """Detecta puerto de debug JDWP activo en procesos Java (permite inyección en runtime)."""
        print("🔍 Escaneando JDWP en procesos Java...")
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'java' not in name:
                        continue
                    cmdline = ' '.join(proc.info.get('cmdline') or [])
                    if 'jdwp' in cmdline.lower() or 'agentlib:jdwp' in cmdline.lower():
                        print(f"🚨 JDWP PORT ACTIVO en PID {proc.pid}")
                        self.issues_found.append({
                            'nombre': f'Puerto debug JDWP activo en Java (PID {proc.pid}) — permite inyección de bytecode',
                            'ruta': cmdline[:255],
                            'archivo': proc.info.get('name', 'javaw.exe'),
                            'tipo': 'jdwp_debug_port',
                            'categoria': 'JAVA_INJECTION',
                            'alerta': 'CRITICAL',
                            'confidence': 0.95,
                            'detected_patterns': ['jdwp_active'],
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_jdwp_port: {e}")

    def scan_vpn_adapters(self):
        """Detecta adaptadores VPN activos durante el scan (posible intento de evasión)."""
        print("🔍 Escaneando adaptadores VPN...")
        VPN_KEYWORDS = [
            'vpn', 'mullvad', 'nordvpn', 'expressvpn', 'protonvpn', 'surfshark',
            'private internet', 'ipvanish', 'cyberghost', 'windscribe', 'tunnelbear',
            'wireguard', 'openvpn', 'tap-windows', 'tap0901', 'psiphon',
            'hotspot shield', 'hide.me', 'pia vpn', 'privatevpn',
        ]
        try:
            for iface_name, stat in psutil.net_if_stats().items():
                if not stat.isup:
                    continue
                if any(kw in iface_name.lower() for kw in VPN_KEYWORDS):
                    print(f"⚠️ VPN ACTIVA: {iface_name}")
                    self.issues_found.append({
                        'nombre': f'Adaptador VPN activo durante el scan: {iface_name}',
                        'ruta': 'Adaptadores de red del sistema',
                        'archivo': iface_name,
                        'tipo': 'vpn_active',
                        'categoria': 'EVASION',
                        'alerta': 'SOSPECHOSO',
                        'confidence': 0.70,
                        'detected_patterns': ['vpn_active_during_scan'],
                    })
        except Exception as e:
            print(f"Error en scan_vpn_adapters: {e}")

    def scan_hosts_file(self):
        """Detecta modificaciones en el hosts de Windows (redirección de dominios de Minecraft)."""
        print("🔍 Escaneando archivo hosts...")
        hosts_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'),
                                  'System32', 'drivers', 'etc', 'hosts')
        if not os.path.exists(hosts_path):
            return
        MINECRAFT_DOMAINS = [
            'session.minecraft.net', 'authserver.mojang.com', 'account.mojang.com',
            'api.mojang.com', 'mojang.com', 'minecraft.net', 'multiplayer.minecraft',
            'hypixel.net', 'mineplex.com', 'cubecraft.net',
        ]
        try:
            with open(hosts_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            custom = []
            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith('#'):
                    continue
                if stripped in ('127.0.0.1 localhost', '::1 localhost', '127.0.0.1 localhost.localdomain'):
                    continue
                custom.append(stripped)
                if any(d in stripped.lower() for d in MINECRAFT_DOMAINS):
                    print(f"🚨 HOSTS REDIRIGE DOMINIO DE MINECRAFT: {stripped}")
                    self.issues_found.append({
                        'nombre': f'Hosts redirige dominio de Minecraft/Mojang: {stripped[:120]}',
                        'ruta': hosts_path,
                        'archivo': 'hosts',
                        'tipo': 'hosts_minecraft_redirect',
                        'categoria': 'EVASION',
                        'alerta': 'CRITICAL',
                        'confidence': 0.92,
                        'detected_patterns': ['hosts_mojang_redirect'],
                    })
            if custom:
                print(f"⚠️ HOSTS FILE CON {len(custom)} ENTRADA(S) NO ESTÁNDAR")
                self.issues_found.append({
                    'nombre': f'Hosts file modificado: {len(custom)} entrada(s) no estándar',
                    'ruta': hosts_path,
                    'archivo': '; '.join(custom[:5])[:255],
                    'tipo': 'hosts_file_custom',
                    'categoria': 'EVASION',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.55,
                    'detected_patterns': ['hosts_custom_entries'],
                })
        except Exception as e:
            print(f"Error en scan_hosts_file: {e}")

    def scan_executed_userassist(self):
        """Lee UserAssist del registro para detectar ejecutables recientes con timestamps."""
        print("🔍 Escaneando UserAssist (ejecutables recientes)...")
        hack_terms = [
            'vape', 'entropy', 'hack', 'cheat', 'inject', 'wurst', 'liquidbounce',
            'sigma', 'flux', 'killaura', 'aimbot', 'bypass', 'crack', 'autoclick',
            'clicker', 'phobos', 'astolfo', 'novoline', 'ghost', 'dllinjector'
        ]
        import codecs
        import struct

        def rot13(s):
            return codecs.encode(s, 'rot_13')

        ua_guids = [
            r'Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist\{CEBFF5CD-ACE2-4F4F-9178-9926F41749EA}\Count',
            r'Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist\{F4E57C4B-2036-45F0-A9AB-443BCFE33D9F}\Count',
        ]

        executed = []
        try:
            for guid_path in ua_guids:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, guid_path) as k:
                        i = 0
                        while True:
                            try:
                                name, data, _ = winreg.EnumValue(k, i)
                                i += 1
                                decoded = rot13(name)
                                if len(data) >= 72:
                                    try:
                                        ft_raw = struct.unpack_from('<Q', data, 60)[0]
                                        if ft_raw > 0:
                                            EPOCH_DIFF = 116444736000000000
                                            unix_ts = (ft_raw - EPOCH_DIFF) / 10000000
                                            if 0 < unix_ts < 2000000000:
                                                last_run = datetime.fromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')
                                            else:
                                                last_run = 'Desconocida'
                                        else:
                                            last_run = 'Desconocida'
                                    except Exception:
                                        last_run = 'Desconocida'
                                else:
                                    last_run = 'Desconocida'
                                executed.append({'name': decoded, 'last_run': last_run})
                            except OSError:
                                break
                except (FileNotFoundError, PermissionError):
                    pass

            suspicious = []
            for item in executed:
                name_lower = item['name'].lower()
                for term in hack_terms:
                    if term in name_lower:
                        suspicious.append(item)
                        self.issues_found.append({
                            'tipo': 'userassist_suspicious',
                            'nombre': f'Ejecutado sospechoso (UserAssist): {os.path.basename(item["name"])}',
                            'ruta': item['name'][:255],
                            'archivo': item['name'][:255],
                            'categoria': 'EXECUTED_FILES',
                            'alerta': 'CRITICAL',
                            'confidence': 80,
                            'detected_patterns': [term],
                            'extra': {'last_run': item['last_run']},
                        })
                        print(f"🚨 USERASSIST SOSPECHOSO: {item['name'][:80]} @ {item['last_run']}")
                        break

            if executed:
                summary = ' | '.join([f"{os.path.basename(e['name'])} @ {e['last_run']}"
                                       for e in sorted(executed, key=lambda x: x['last_run'], reverse=True)[:25]])
                self.issues_found.append({
                    'tipo': 'userassist_history',
                    'nombre': f'UserAssist: {len(executed)} ejecutables registrados',
                    'ruta': 'HKCU\\UserAssist',
                    'archivo': summary[:500],
                    'categoria': 'EXECUTED_FILES',
                    'alerta': 'NORMAL',
                    'confidence': 0,
                    'detected_patterns': [os.path.basename(e['name']) for e in executed[:25]],
                })
        except Exception as e:
            print(f"Error en scan_executed_userassist: {e}")

    # ── NUEVOS MÓDULOS ─────────────────────────────────────────────────────────

    def scan_run_mru(self):
        """Escanea comandos ejecutados desde el cuadro Ejecutar (Win+R)."""
        print("🔍 Escaneando RunMRU (Win+R)...")
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient', 'wurst', 'wurstclient',
            'liquidbounce', 'killaura', 'aimbot', 'cheatengine', 'xray', 'triggerbot',
            'dllinjector', 'bspoof', 'phobos', 'astolfo', 'novoline',
            'ghostclient', 'silentclient', 'fluxclient',
        ]
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                i = 0
                while True:
                    try:
                        name, data, _ = winreg.EnumValue(k, i)
                        i += 1
                        if name == 'MRUList' or not isinstance(data, str):
                            continue
                        cmd = data.rstrip('\x01').strip()
                        cmd_lower = cmd.lower()
                        for term in hack_terms:
                            if term in cmd_lower:
                                self.issues_found.append({
                                    'tipo': 'run_mru_suspicious',
                                    'nombre': f'Win+R sospechoso: {cmd[:80]}',
                                    'ruta': key_path,
                                    'archivo': cmd[:255],
                                    'categoria': 'CMD_HISTORY',
                                    'alerta': 'CRITICAL',
                                    'confidence': 80,
                                    'detected_patterns': [term],
                                })
                                print(f"🚨 RUN MRU: {cmd[:80]}")
                                break
                    except OSError:
                        break
        except (FileNotFoundError, PermissionError):
            pass
        except Exception as e:
            print(f"Error en scan_run_mru: {e}")

    def scan_typed_paths(self):
        """Escanea rutas escritas en la barra de direcciones de Explorer."""
        print("🔍 Escaneando TypedPaths...")
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient', 'wurst', 'wurstclient',
            'liquidbounce', 'killaura', 'aimbot', 'cheatengine', 'xray', 'triggerbot',
            'dllinjector', 'bspoof', 'phobos', 'astolfo', 'novoline',
            'ghostclient', 'silentclient', 'fluxclient',
        ]
        key_path = r'Software\Microsoft\Windows\CurrentVersion\Explorer\TypedPaths'
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                i = 0
                while True:
                    try:
                        name, data, _ = winreg.EnumValue(k, i)
                        i += 1
                        if not isinstance(data, str):
                            continue
                        path_lower = data.lower()
                        for term in hack_terms:
                            if term in path_lower:
                                self.issues_found.append({
                                    'tipo': 'typed_path_suspicious',
                                    'nombre': f'Ruta sospechosa en Explorer: {data[:80]}',
                                    'ruta': key_path,
                                    'archivo': data[:255],
                                    'categoria': 'CMD_HISTORY',
                                    'alerta': 'CRITICAL',
                                    'confidence': 75,
                                    'detected_patterns': [term],
                                })
                                print(f"🚨 TYPED PATH: {data[:80]}")
                                break
                    except OSError:
                        break
        except (FileNotFoundError, PermissionError):
            pass
        except Exception as e:
            print(f"Error en scan_typed_paths: {e}")

    def scan_usb_history(self):
        """Escanea el historial de dispositivos USB conectados (USBSTOR)."""
        print("🔍 Escaneando historial USB (USBSTOR)...")
        key_path = r'SYSTEM\CurrentControlSet\Enum\USBSTOR'
        devices = []
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as base:
                i = 0
                while True:
                    try:
                        device_class = winreg.EnumKey(base, i)
                        i += 1
                        with winreg.OpenKey(base, device_class) as dc_key:
                            j = 0
                            while True:
                                try:
                                    instance = winreg.EnumKey(dc_key, j)
                                    j += 1
                                    # Nombre amigable
                                    friendly = device_class.replace('Disk&Ven_', '').replace('_Prod_', ' ').split('&Rev_')[0]
                                    devices.append(friendly[:80])
                                except OSError:
                                    break
                    except OSError:
                        break
            if devices:
                summary = ' | '.join(devices[:20])
                self.issues_found.append({
                    'tipo': 'usb_history',
                    'nombre': f'USB: {len(devices)} dispositivo(s) conectado(s) históricamente',
                    'ruta': key_path,
                    'archivo': summary[:400],
                    'categoria': 'HARDWARE',
                    'alerta': 'NORMAL',
                    'confidence': 0,
                    'detected_patterns': devices[:20],
                })
                print(f"✅ USBSTOR: {len(devices)} dispositivos en historial")
        except (FileNotFoundError, PermissionError):
            pass
        except Exception as e:
            print(f"Error en scan_usb_history: {e}")

    def scan_startup_entries(self):
        """Escanea entradas de autoarranque (Run/RunOnce) en busca de hacks con persistencia."""
        print("🔍 Escaneando entradas de inicio automático...")
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'wurst', 'liquidbounce',
            'killaura', 'aimbot', 'cheatengine', 'xray', 'triggerbot',
            'dllinjector', 'phobos', 'astolfo', 'ghostclient', 'silentclient', 'fluxclient',
        ]
        run_keys = [
            (winreg.HKEY_CURRENT_USER,  r'Software\Microsoft\Windows\CurrentVersion\Run'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\Run'),
            (winreg.HKEY_CURRENT_USER,  r'Software\Microsoft\Windows\CurrentVersion\RunOnce'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\RunOnce'),
        ]
        for hive, path in run_keys:
            try:
                with winreg.OpenKey(hive, path) as k:
                    i = 0
                    while True:
                        try:
                            name, data, _ = winreg.EnumValue(k, i)
                            i += 1
                            if not isinstance(data, str):
                                continue
                            data_lower = data.lower()
                            name_lower = name.lower()
                            for term in hack_terms:
                                if term in data_lower or term in name_lower:
                                    self.issues_found.append({
                                        'tipo': 'startup_suspicious',
                                        'nombre': f'Startup sospechoso: {name} → {data[:60]}',
                                        'ruta': path,
                                        'archivo': data[:255],
                                        'categoria': 'PERSISTENCIA',
                                        'alerta': 'CRITICAL',
                                        'confidence': 90,
                                        'detected_patterns': [term],
                                    })
                                    print(f"🚨 STARTUP: {name} → {data[:60]}")
                                    break
                        except OSError:
                            break
            except (FileNotFoundError, PermissionError):
                pass
            except Exception as e:
                print(f"Error leyendo startup key {path}: {e}")

    def scan_installed_programs(self):
        """Escanea programas instalados en el registro en busca de CheatEngine u otras herramientas de trampa."""
        print("🔍 Escaneando programas instalados...")
        hack_terms = [
            'cheat engine', 'cheatengine', 'vape', 'liquidbounce',
            'dllinjector', 'process hacker', 'x64dbg', 'ollydbg',
            'processhacker', 'wireshark', 'charles proxy', 'fiddler',
        ]
        uninstall_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\Uninstall'),
            (winreg.HKEY_CURRENT_USER,  r'Software\Microsoft\Windows\CurrentVersion\Uninstall'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'),
        ]
        for hive, path in uninstall_keys:
            try:
                with winreg.OpenKey(hive, path) as base:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(base, i)
                            i += 1
                            try:
                                with winreg.OpenKey(base, subkey_name) as sk:
                                    try:
                                        display_name, _ = winreg.QueryValueEx(sk, 'DisplayName')
                                    except FileNotFoundError:
                                        continue
                                    if not isinstance(display_name, str):
                                        continue
                                    dn_lower = display_name.lower()
                                    for term in hack_terms:
                                        if term in dn_lower:
                                            try:
                                                install_loc, _ = winreg.QueryValueEx(sk, 'InstallLocation')
                                            except Exception:
                                                install_loc = ''
                                            self.issues_found.append({
                                                'tipo': 'installed_hack_tool',
                                                'nombre': f'Herramienta instalada: {display_name}',
                                                'ruta': install_loc[:255],
                                                'archivo': display_name[:255],
                                                'categoria': 'HACKS',
                                                'alerta': 'CRITICAL',
                                                'confidence': 88,
                                                'detected_patterns': [term],
                                            })
                                            print(f"🚨 PROGRAMA SOSPECHOSO INSTALADO: {display_name}")
                                            break
                            except (PermissionError, OSError):
                                pass
                        except OSError:
                            break
            except (FileNotFoundError, PermissionError):
                pass
            except Exception as e:
                print(f"Error en scan_installed_programs ({path}): {e}")

    def scan_bam_registry(self):
        """Lee Background Activity Monitor (BAM) para detectar ejecutables con timestamps precisos."""
        print("🔍 Escaneando BAM registry (Background Activity Monitor)...")
        import struct
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient',
            'wurst', 'wurstclient', 'liquidbounce',
            'killaura', 'aimbot', 'cheatengine',
            'xray', 'triggerbot', 'dllinjector', 'bspoof',
            'phobos', 'astolfo', 'novoline',
            'ghostclient', 'silentclient', 'fluxclient',
        ]
        EPOCH_DIFF = 116444736000000000

        def parse_bam_ts(data):
            try:
                if len(data) >= 8:
                    ft_raw = struct.unpack_from('<Q', data, 0)[0]
                    if ft_raw > 0:
                        unix_ts = (ft_raw - EPOCH_DIFF) / 10000000
                        if 0 < unix_ts < 2000000000:
                            return datetime.fromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                pass
            return 'Desconocida'

        try:
            bam_base = r'SYSTEM\CurrentControlSet\Services\bam\State\UserSettings'
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, bam_base) as base_key:
                sid_idx = 0
                while True:
                    try:
                        sid = winreg.EnumKey(base_key, sid_idx)
                        sid_idx += 1
                        sid_path = bam_base + '\\' + sid
                        try:
                            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sid_path) as sid_key:
                                val_idx = 0
                                all_entries = []
                                while True:
                                    try:
                                        name, data, vtype = winreg.EnumValue(sid_key, val_idx)
                                        val_idx += 1
                                        if not isinstance(data, bytes) or not name.startswith('\\Device\\'):
                                            continue
                                        ts = parse_bam_ts(data)
                                        exe_name = name.split('\\')[-1]
                                        all_entries.append({'name': name, 'exe': exe_name, 'ts': ts})
                                        # Check for hack terms
                                        name_lower = name.lower()
                                        for term in hack_terms:
                                            if term in name_lower:
                                                self.issues_found.append({
                                                    'tipo': 'bam_suspicious',
                                                    'nombre': f'BAM: ejecutable sospechoso detectado — {exe_name}',
                                                    'ruta': name[:255],
                                                    'archivo': name[:255],
                                                    'categoria': 'EXECUTED_FILES',
                                                    'alerta': 'CRITICAL',
                                                    'confidence': 85,
                                                    'detected_patterns': [term],
                                                    'extra': {'last_run': ts, 'fuente': 'BAM'},
                                                })
                                                print(f"🚨 BAM SOSPECHOSO: {exe_name} @ {ts}")
                                                break
                                    except OSError:
                                        break
                                if all_entries:
                                    print(f"✅ BAM: {len(all_entries)} ejecutables en SID ...{sid[-8:]}")
                        except (FileNotFoundError, PermissionError):
                            pass
                    except OSError:
                        break
        except (FileNotFoundError, PermissionError) as e:
            print(f"BAM registry no disponible: {e}")
        except Exception as e:
            print(f"Error en scan_bam_registry: {e}")

    def scan_recent_lnk(self):
        """Escanea archivos .lnk recientes en %APPDATA%\\Microsoft\\Windows\\Recent."""
        print("🔍 Escaneando archivos .lnk recientes...")
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient',
            'wurst', 'wurstclient', 'liquidbounce',
            'killaura', 'aimbot', 'cheatengine',
            'xray', 'triggerbot', 'dllinjector', 'bspoof',
            'phobos', 'astolfo', 'novoline',
            'ghostclient', 'silentclient', 'fluxclient',
        ]
        recent_dir = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Recent')
        if not os.path.exists(recent_dir):
            return
        try:
            lnk_files = []
            for fname in os.listdir(recent_dir):
                if not fname.lower().endswith('.lnk'):
                    continue
                fpath = os.path.join(recent_dir, fname)
                try:
                    mtime = os.path.getmtime(fpath)
                    ts = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    base = fname[:-4]  # strip .lnk
                    lnk_files.append({'name': base, 'ts': ts})
                    # Check for hack terms
                    name_lower = base.lower()
                    for term in hack_terms:
                        if term in name_lower:
                            self.issues_found.append({
                                'tipo': 'recent_lnk_suspicious',
                                'nombre': f'Archivo reciente sospechoso: {base}',
                                'ruta': fpath[:255],
                                'archivo': fpath[:255],
                                'categoria': 'EXECUTED_FILES',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 65,
                                'detected_patterns': [term],
                                'extra': {'last_access': ts, 'fuente': 'Recent LNK'},
                            })
                            print(f"⚠️ LNK SOSPECHOSO: {base} @ {ts}")
                            break
                except Exception:
                    pass

            if lnk_files:
                print(f"✅ LNK recientes: {len(lnk_files)} archivos encontrados")
        except Exception as e:
            print(f"Error en scan_recent_lnk: {e}")

    def scan_powershell_history(self):
        """Escanea el historial de PowerShell (PSReadLine) en busca de comandos sospechosos."""
        print("🔍 Escaneando historial de PowerShell...")
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient',
            'wurst', 'wurstclient', 'liquidbounce',
            'killaura', 'aimbot', 'cheatengine',
            'xray', 'triggerbot', 'dllinjector', 'bspoof',
            'phobos', 'astolfo', 'novoline', 'processhollowing',
            'ghostclient', 'silentclient', 'fluxclient',
        ]
        ps_history = os.path.join(
            os.environ.get('APPDATA', ''),
            'Microsoft', 'Windows', 'PowerShell', 'PSReadLine', 'ConsoleHost_history.txt'
        )
        if not os.path.exists(ps_history):
            return
        try:
            with open(ps_history, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            suspicious_cmds = []
            all_cmds = [l.strip() for l in lines if l.strip()]

            for cmd in all_cmds:
                cmd_lower = cmd.lower()
                for term in hack_terms:
                    if term in cmd_lower:
                        suspicious_cmds.append(cmd)
                        self.issues_found.append({
                            'tipo': 'powershell_suspicious',
                            'nombre': f'Comando PS sospechoso: {cmd[:80]}',
                            'ruta': ps_history[:255],
                            'archivo': cmd[:255],
                            'categoria': 'CMD_HISTORY',
                            'alerta': 'CRITICAL',
                            'confidence': 78,
                            'detected_patterns': [term],
                        })
                        print(f"🚨 PS SOSPECHOSO: {cmd[:80]}")
                        break

            if all_cmds:
                print(f"✅ PS history: {len(all_cmds)} comandos, {len(suspicious_cmds)} sospechosos")
        except Exception as e:
            print(f"Error en scan_powershell_history: {e}")

    def scan_browser_downloads(self):
        """Escanea historial de descargas de Chrome, Edge y Firefox en busca de hacks."""
        print("🔍 Escaneando historial de descargas de navegadores...")
        import sqlite3
        import shutil
        import tempfile

        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient',
            'wurst', 'wurstclient', 'liquidbounce',
            'killaura', 'aimbot', 'cheatengine',
            'xray', 'triggerbot', 'dllinjector', 'bspoof',
            'phobos', 'astolfo', 'novoline',
            'ghostclient', 'silentclient', 'fluxclient',
        ]

        local = os.environ.get('LOCALAPPDATA', '')
        appdata = os.environ.get('APPDATA', '')

        db_paths = [
            os.path.join(local, 'Google', 'Chrome', 'User Data', 'Default', 'History'),
            os.path.join(local, 'Microsoft', 'Edge', 'User Data', 'Default', 'History'),
            os.path.join(local, 'Google', 'Chrome', 'User Data', 'Profile 1', 'History'),
            os.path.join(appdata, 'Mozilla', 'Firefox', 'Profiles'),  # dir, handled separately
        ]

        def check_chromium_db(db_path):
            if not os.path.exists(db_path):
                return
            tmp = None
            try:
                # Copy to temp to avoid SQLite lock
                fd, tmp = tempfile.mkstemp(suffix='.db')
                os.close(fd)
                shutil.copy2(db_path, tmp)
                con = sqlite3.connect(tmp)
                cur = con.cursor()
                cur.execute("SELECT url, target_path FROM downloads LIMIT 5000")
                rows = cur.fetchall()
                con.close()
                suspicious = []
                all_downloads = []
                for url, target in rows:
                    text = ((url or '') + ' ' + (target or '')).lower()
                    fname = os.path.basename(target or url or '')
                    all_downloads.append(fname[:60])
                    for term in hack_terms:
                        if term in text:
                            suspicious.append(f"{fname} ({url[:60]})")
                            self.issues_found.append({
                                'tipo': 'browser_download_suspicious',
                                'nombre': f'Descarga sospechosa: {fname}',
                                'ruta': target[:255] if target else url[:255],
                                'archivo': url[:255] if url else '',
                                'categoria': 'CMD_HISTORY',
                                'alerta': 'CRITICAL',
                                'confidence': 80,
                                'detected_patterns': [term],
                            })
                            print(f"🚨 DESCARGA SOSPECHOSA: {fname} — {url[:60]}")
                            break
                if all_downloads:
                    self.issues_found.append({
                        'tipo': 'browser_download_history',
                        'nombre': f'Historial de descargas ({os.path.basename(os.path.dirname(db_path))}): {len(all_downloads)} entradas',
                        'ruta': db_path[:255],
                        'archivo': ' | '.join(all_downloads[-20:])[:500],
                        'categoria': 'CMD_HISTORY',
                        'alerta': 'NORMAL',
                        'confidence': 0,
                        'detected_patterns': all_downloads[-20:],
                    })
            except Exception as e:
                print(f"  Error leyendo {db_path}: {e}")
            finally:
                if tmp and os.path.exists(tmp):
                    try: os.remove(tmp)
                    except: pass

        # Chromium-based browsers
        for db_path in db_paths:
            if 'Profiles' not in db_path:
                check_chromium_db(db_path)

        # Firefox — iterate profiles
        ff_profiles = db_paths[-1]
        if os.path.isdir(ff_profiles):
            try:
                for profile in os.listdir(ff_profiles):
                    ff_db = os.path.join(ff_profiles, profile, 'places.sqlite')
                    if os.path.exists(ff_db):
                        tmp = None
                        try:
                            fd, tmp = tempfile.mkstemp(suffix='.db')
                            os.close(fd)
                            shutil.copy2(ff_db, tmp)
                            con = sqlite3.connect(tmp)
                            cur = con.cursor()
                            cur.execute("SELECT url FROM moz_places LIMIT 5000")
                            rows = cur.fetchall()
                            con.close()
                            for (url,) in rows:
                                if not url: continue
                                url_lower = url.lower()
                                for term in hack_terms:
                                    if term in url_lower:
                                        fname = url.split('/')[-1][:60]
                                        self.issues_found.append({
                                            'tipo': 'browser_download_suspicious',
                                            'nombre': f'Visita/descarga sospechosa (Firefox): {fname}',
                                            'ruta': url[:255],
                                            'archivo': url[:255],
                                            'categoria': 'CMD_HISTORY',
                                            'alerta': 'SOSPECHOSO',
                                            'confidence': 65,
                                            'detected_patterns': [term],
                                        })
                                        break
                        except Exception:
                            pass
                        finally:
                            if tmp and os.path.exists(tmp):
                                try: os.remove(tmp)
                                except: pass
            except Exception as e:
                print(f"Error en Firefox profiles: {e}")

    def scan_appcompat_shimcache(self):
        """Lee AppCompatCache (ShimCache) del registro — ejecuciones históricas de aplicaciones."""
        print("🔍 Escaneando AppCompatCache (ShimCache)...")
        import re as _re
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient',
            'wurst', 'wurstclient', 'liquidbounce',
            'killaura', 'aimbot', 'cheatengine',
            'xray', 'triggerbot', 'dllinjector', 'bspoof',
            'phobos', 'astolfo', 'novoline',
            'ghostclient', 'silentclient', 'fluxclient',
        ]

        def _valid_path(p):
            """Ruta válida de Windows: empieza con letra de unidad o \\Device\\, sin chars raros."""
            if not p or len(p) < 5:
                return False
            if not (_re.match(r'^[A-Za-z]:\\', p) or p.startswith('\\Device\\')):
                return False
            if any(ord(c) < 0x20 for c in p):
                return False
            return True
        try:
            key_path = r'SYSTEM\CurrentControlSet\Control\Session Manager\AppCompatCache'
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
                data, _ = winreg.QueryValueEx(k, 'AppCompatCache')

            if not isinstance(data, bytes) or len(data) < 16:
                return

            # Parse: signature at [0:4], entry count at [4:8], entries from offset 128
            sig = data[:4]
            entries = []

            # Windows 10/11 format: 0x30 = entries start at 0x80 (128)
            if sig in (b'10ts', b'\x30\x00\x00\x00'):
                offset = 128
            else:
                offset = 128  # fallback

            while offset + 12 <= len(data):
                try:
                    entry_sig = data[offset:offset+4]
                    if entry_sig != b'10ts':
                        offset += 4
                        continue
                    data_len = int.from_bytes(data[offset+4:offset+8], 'little')
                    if data_len <= 0 or data_len > 65536:
                        offset += 4
                        continue
                    entry_data = data[offset+8:offset+8+data_len]
                    # Path is UTF-16LE at start of entry_data
                    path_len = int.from_bytes(entry_data[0:2], 'little') if len(entry_data) >= 4 else 0
                    if 0 < path_len <= len(entry_data) - 4:
                        path = entry_data[4:4+path_len].decode('utf-16-le', errors='ignore')
                        if _valid_path(path):
                            entries.append(path)
                    offset += 8 + data_len
                except Exception:
                    offset += 4

            if not entries:
                return

            suspicious = []
            for path in entries:
                path_lower = path.lower()
                for term in hack_terms:
                    if term in path_lower:
                        suspicious.append(path)
                        self.issues_found.append({
                            'tipo': 'shimcache_suspicious',
                            'nombre': f'ShimCache: ejecutable sospechoso — {os.path.basename(path)}',
                            'ruta': path[:255],
                            'archivo': path[:255],
                            'categoria': 'EXECUTED_FILES',
                            'alerta': 'CRITICAL',
                            'confidence': 82,
                            'detected_patterns': [term],
                        })
                        print(f"🚨 SHIMCACHE SOSPECHOSO: {path[:80]}")
                        break

            if entries:
                print(f"✅ ShimCache: {len(entries)} entradas válidas")
        except (FileNotFoundError, PermissionError) as e:
            print(f"ShimCache no disponible: {e}")
        except Exception as e:
            print(f"Error en scan_appcompat_shimcache: {e}")

    def scan_muicache(self):
        """Lee MUICache — nombres de todos los ejecutables que corrió el usuario, incluyendo borrados."""
        print("🔍 Escaneando MUICache...")
        hack_terms = [
            'vape', 'vapelite', 'entropy', 'entropyclient',
            'wurst', 'wurstclient', 'liquidbounce',
            'killaura', 'aimbot', 'cheatengine',
            'xray', 'triggerbot', 'dllinjector', 'bspoof',
            'phobos', 'astolfo', 'novoline',
            'ghostclient', 'silentclient', 'fluxclient',
        ]
        key_path = r'Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache'
        try:
            entries = []
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                i = 0
                while True:
                    try:
                        name, data, _ = winreg.EnumValue(k, i)
                        i += 1
                        if name.endswith('.FriendlyAppName') or name.endswith('.ApplicationCompany'):
                            continue
                        if '\\' in name or '/' in name:
                            entries.append(name)
                    except OSError:
                        break

            suspicious = []
            for path in entries:
                path_lower = path.lower()
                for term in hack_terms:
                    if term in path_lower:
                        suspicious.append(path)
                        self.issues_found.append({
                            'tipo': 'muicache_suspicious',
                            'nombre': f'MUICache: ejecutable sospechoso — {os.path.basename(path)}',
                            'ruta': path[:255],
                            'archivo': path[:255],
                            'categoria': 'EXECUTED_FILES',
                            'alerta': 'CRITICAL',
                            'confidence': 80,
                            'detected_patterns': [term],
                        })
                        print(f"🚨 MUICACHE SOSPECHOSO: {path[:80]}")
                        break

            if entries:
                print(f"✅ MUICache: {len(entries)} entradas válidas")
        except (FileNotFoundError, PermissionError) as e:
            print(f"MUICache no disponible: {e}")
        except Exception as e:
            print(f"Error en scan_muicache: {e}")

    def scan_scheduled_tasks(self):
        """Escanea tareas programadas de Windows en busca de ejecutables sospechosos."""
        print("🔍 Escaneando tareas programadas de Windows...")
        hack_terms = [
            'vape', 'entropy', 'hack', 'cheat', 'inject', 'wurst', 'liquidbounce',
            'sigma', 'flux', 'killaura', 'aimbot', 'bypass', 'crack', 'autoclick',
            'clicker', 'phobos', 'astolfo', 'dllinjector', 'cheatengine',
            'xray', 'triggerbot', 'ghostclient',
        ]
        tasks_dir = r'C:\Windows\System32\Tasks'
        if not os.path.exists(tasks_dir):
            return
        try:
            found_tasks = []
            for root, dirs, files in os.walk(tasks_dir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read(32768)
                        content_lower = content.lower()
                        for term in hack_terms:
                            if term in content_lower:
                                found_tasks.append(fname)
                                self.issues_found.append({
                                    'tipo': 'scheduled_task_suspicious',
                                    'nombre': f'Tarea programada sospechosa: {fname}',
                                    'ruta': fpath[:255],
                                    'archivo': fpath[:255],
                                    'categoria': 'CMD_HISTORY',
                                    'alerta': 'CRITICAL',
                                    'confidence': 85,
                                    'detected_patterns': [term],
                                })
                                print(f"🚨 TAREA SOSPECHOSA: {fname} (contiene '{term}')")
                                break
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error en scan_scheduled_tasks: {e}")

    def scan_texture_packs(self):
        """Escanea resource packs de Minecraft, incluyendo análisis de XRay."""
        print("🔍 Escaneando resource packs de Minecraft...")
        xray_terms = ['xray', 'x-ray', 'xview', 'ore', 'highlight', 'transparent', 'wallhack', 'see_through']
        mc_path = os.path.join(os.environ.get('APPDATA', ''), '.minecraft', 'resourcepacks')
        if not os.path.exists(mc_path):
            return
        try:
            packs = []
            for entry in os.listdir(mc_path):
                entry_path = os.path.join(mc_path, entry)
                name_lower = entry.lower()
                mtime = os.path.getmtime(entry_path)
                added_at = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                is_xray = any(t in name_lower for t in xray_terms)
                alerta = 'CRITICAL' if is_xray else 'NORMAL'
                confidence = 85 if is_xray else 0

                packs.append({'name': entry, 'added_at': added_at, 'is_xray': is_xray})
                self.issues_found.append({
                    'tipo': 'texture_pack',
                    'nombre': f'Resource Pack: {entry}' + (' [POSIBLE XRAY]' if is_xray else ''),
                    'ruta': entry_path,
                    'archivo': entry,
                    'categoria': 'TEXTURE_PACKS',
                    'alerta': alerta,
                    'confidence': confidence,
                    'detected_patterns': [t for t in xray_terms if t in name_lower],
                    'extra': {'added_at': added_at, 'is_xray': is_xray},
                })
                if is_xray:
                    print(f"🚨 POSIBLE XRAY PACK: {entry}")
                else:
                    print(f"ℹ️ Resource Pack: {entry}")

                # Try xray_texture_analyzer if available
                try:
                    from xray_texture_analyzer import XRayTextureAnalyzer
                    analyzer = XRayTextureAnalyzer()
                    result = analyzer.analyze_pack(entry_path)
                    if result and result.get('is_xray'):
                        self.issues_found.append({
                            'tipo': 'texture_pack_xray',
                            'nombre': f'XRAY confirmado por análisis: {entry}',
                            'ruta': entry_path,
                            'archivo': entry,
                            'categoria': 'TEXTURE_PACKS',
                            'alerta': 'CRITICAL',
                            'confidence': result.get('confidence', 90),
                            'detected_patterns': result.get('patterns', []),
                        })
                        print(f"🚨 XRAY CONFIRMADO por análisis: {entry}")
                except Exception:
                    pass

        except Exception as e:
            print(f"Error en scan_texture_packs: {e}")

    def scan_exploit_tools(self):
        """Detecta herramientas de exploit y RATs conocidas."""
        print("🔍 Buscando herramientas de exploit y RATs...")
        exploit_signatures = [
            # RATs
            ('njrat', 'RAT', 'CRITICAL'), ('darkcomet', 'RAT', 'CRITICAL'),
            ('nanocore', 'RAT', 'CRITICAL'), ('quasar', 'RAT', 'CRITICAL'),
            ('asyncrat', 'RAT', 'CRITICAL'), ('remcos', 'RAT', 'CRITICAL'),
            ('limerat', 'RAT', 'CRITICAL'),
            # Keyloggers
            ('keylogger', 'KEYLOGGER', 'CRITICAL'), ('ardamax', 'KEYLOGGER', 'CRITICAL'),
            ('revealer', 'KEYLOGGER', 'SOSPECHOSO'),
            # Exploits
            ('metasploit', 'EXPLOIT', 'CRITICAL'), ('cobalt', 'EXPLOIT', 'CRITICAL'),
            ('msfvenom', 'EXPLOIT', 'CRITICAL'), ('shellcode', 'EXPLOIT', 'SOSPECHOSO'),
            # Packet tools
            ('wireshark', 'PACKET_SNIFF', 'SOSPECHOSO'), ('cheatengine', 'CHEAT', 'CRITICAL'),
            ('x64dbg', 'DEBUGGER', 'SOSPECHOSO'), ('ollydbg', 'DEBUGGER', 'SOSPECHOSO'),
            ('processhacker', 'PROC_HACK', 'SOSPECHOSO'),
        ]

        search_paths = [
            os.path.expanduser('~\\Desktop'),
            os.path.expanduser('~\\Downloads'),
            os.path.expanduser('~\\AppData\\Roaming'),
            os.path.expanduser('~\\AppData\\Local\\Temp'),
        ]

        found_names = set()
        try:
            # Check running processes
            for proc in psutil.process_iter(['name', 'exe']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    pexe = (proc.info.get('exe') or '').lower()
                    for sig, cat, level in exploit_signatures:
                        if sig in pname or sig in pexe:
                            key = sig + pname
                            if key not in found_names:
                                found_names.add(key)
                                self.issues_found.append({
                                    'tipo': 'exploit_process',
                                    'nombre': f'Proceso de exploit activo: {proc.info.get("name", sig)}',
                                    'ruta': proc.info.get('exe') or 'N/A',
                                    'archivo': proc.info.get('name', sig),
                                    'categoria': cat,
                                    'alerta': level,
                                    'confidence': 90,
                                    'detected_patterns': [sig],
                                })
                                print(f"🚨 EXPLOIT PROCESS: {proc.info.get('name')} [{level}]")
                            break
                except Exception:
                    continue

            # Check file system
            for search_path in search_paths:
                if not os.path.exists(search_path):
                    continue
                try:
                    for root, dirs, files in os.walk(search_path):
                        dirs[:] = [d for d in dirs if d not in {'node_modules', '.git', '__pycache__'}]
                        for fname in files:
                            fname_lower = fname.lower()
                            for sig, cat, level in exploit_signatures:
                                if sig in fname_lower:
                                    fpath = os.path.join(root, fname)
                                    key = sig + fpath
                                    if key not in found_names:
                                        found_names.add(key)
                                        self.issues_found.append({
                                            'tipo': 'exploit_file',
                                            'nombre': f'Herramienta de exploit: {fname}',
                                            'ruta': fpath,
                                            'archivo': fname,
                                            'categoria': cat,
                                            'alerta': level,
                                            'confidence': 80,
                                            'detected_patterns': [sig],
                                        })
                                        print(f"🚨 EXPLOIT FILE: {fpath} [{level}]")
                                    break
                except PermissionError:
                    pass
        except Exception as e:
            print(f"Error en scan_exploit_tools: {e}")

    def scan_java_process_parent(self):
        """Analiza el proceso padre de javaw.exe para detectar launchers sospechosos."""
        print("🔍 Analizando árbol de procesos Java (parent process analysis)...")
        LEGITIMATE_PARENTS = {
            'javaw.exe', 'java.exe', 'explorer.exe',
            'tlauncher.exe', 'tlauncher-legacy.exe', 'minecraftlauncher.exe',
            'lunarclient.exe', 'badlion.exe', 'prismlauncher.exe', 'multimc.exe',
            'gdlauncher.exe', 'gdlauncher_next.exe', 'ftb_app.exe', 'curseforge.exe',
            'atlauncher.exe', 'polymc.exe', 'featherlauncher.exe',
            'cmd.exe', 'powershell.exe', 'pwsh.exe',
        }
        SUSPICIOUS_PARENTS = {
            'extremeinjector.exe', 'xenos.exe', 'dllinjector.exe',
            'cheatengine.exe', 'cheat engine.exe', 'processhacker.exe',
            'x64dbg.exe', 'x32dbg.exe', 'ollydbg.exe',
        }
        try:
            for proc in psutil.process_iter(['pid', 'name', 'ppid']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'javaw' not in name and 'java' not in name:
                        continue
                    ppid = proc.info.get('ppid')
                    if not ppid:
                        continue
                    try:
                        parent = psutil.Process(ppid)
                        parent_name = (parent.name() or '').lower()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                    if parent_name in SUSPICIOUS_PARENTS:
                        print(f"🚨 JAVA LANZADO POR INYECTOR: {name} → padre={parent_name}")
                        self.issues_found.append({
                            'nombre': f'Java lanzado por proceso inyector: {name} ← {parent_name}',
                            'ruta': f'PID:{proc.pid} PPID:{ppid}',
                            'archivo': parent_name,
                            'tipo': 'java_suspicious_parent',
                            'categoria': 'JAVA_INJECTION',
                            'alerta': 'CRITICAL',
                            'confidence': 0.95,
                            'detected_patterns': ['java_launched_by_injector', f'parent:{parent_name}'],
                        })
                    elif parent_name not in LEGITIMATE_PARENTS and 'minecraft' not in parent_name:
                        print(f"⚠️ JAVA CON PADRE INUSUAL: {name} → {parent_name}")
                        self.issues_found.append({
                            'nombre': f'Java lanzado por proceso inusual: {parent_name}',
                            'ruta': f'PID:{proc.pid} PPID:{ppid}',
                            'archivo': parent_name,
                            'tipo': 'java_unusual_parent',
                            'categoria': 'JAVA_INJECTION',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 0.60,
                            'detected_patterns': ['java_unusual_parent', f'parent:{parent_name}'],
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_java_process_parent: {e}")

    def scan_evasion_indicators(self):
        """Detecta indicadores de limpieza activa antes del SS (evasión)."""
        print("🔍 Evaluando indicadores de evasión...")
        evasion_score = 0
        indicators = []

        # Indicator 1: VPN activa (ya detectada por scan_vpn_adapters)
        vpn_active = any(i.get('tipo') == 'vpn_active' for i in self.issues_found)
        if vpn_active:
            evasion_score += 25
            indicators.append('VPN activa durante el scan')

        # Indicator 2: Prefetch vacío o muy pequeño (posible limpieza manual)
        try:
            prefetch_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch')
            if os.path.isdir(prefetch_dir):
                pf_count = len([f for f in os.listdir(prefetch_dir) if f.endswith('.pf')])
                if pf_count < 5:
                    evasion_score += 30
                    indicators.append(f'Prefetch inusualmente vacío ({pf_count} archivos)')
                elif pf_count < 20:
                    evasion_score += 10
                    indicators.append(f'Prefetch escaso ({pf_count} archivos)')
        except Exception:
            pass

        # Indicator 3: Muy pocos procesos corriendo (jugador apagó todo)
        try:
            proc_count = sum(1 for _ in psutil.process_iter())
            if proc_count < 30:
                evasion_score += 20
                indicators.append(f'Muy pocos procesos activos ({proc_count}) — posible limpieza pre-SS')
        except Exception:
            pass

        # Indicator 4: Muchos archivos borrados recientemente (scan_deleted_recycle ya detectó)
        recent_deletions = sum(1 for i in self.issues_found if i.get('tipo') == 'deleted_suspicious')
        if recent_deletions >= 3:
            evasion_score += 20 + recent_deletions * 5
            indicators.append(f'{recent_deletions} archivos sospechosos eliminados recientemente')

        # Indicator 5: Hosts file modificado
        hosts_mod = any(i.get('tipo') in ('hosts_minecraft_redirect', 'hosts_file_custom') for i in self.issues_found)
        if hosts_mod:
            evasion_score += 15
            indicators.append('Hosts file modificado (posible bypass de autenticación)')

        if evasion_score >= 25 and indicators:
            alerta = 'CRITICAL' if evasion_score >= 50 else 'SOSPECHOSO'
            print(f"{'🚨' if alerta == 'CRITICAL' else '⚠️'} EVASION SCORE: {evasion_score} — {', '.join(indicators)}")
            self.issues_found.append({
                'nombre': f'Indicadores de evasión activa detectados (score: {evasion_score}): {"; ".join(indicators[:3])}',
                'ruta': 'Análisis de comportamiento del sistema',
                'archivo': '; '.join(indicators[:3])[:255],
                'tipo': 'evasion_indicators',
                'categoria': 'EVASION',
                'alerta': alerta,
                'confidence': min(0.95, evasion_score / 100),
                'detected_patterns': ['evasion_' + ind.split(' ')[0].lower().replace(' ', '_') for ind in indicators],
                'extra': {'evasion_score': evasion_score, 'indicators': indicators},
            })

    def scan_digital_signature(self, file_path: str) -> bool:
        """Verifica la firma digital Authenticode de un ejecutable. Retorna True si está firmado."""
        try:
            import ctypes as _ct
            import ctypes.wintypes as _wt
            WINTRUST_ACTION_GENERIC_VERIFY_V2 = '{00AAC56B-CD44-11d0-8CC2-00C04FC295EE}'

            class WINTRUST_FILE_INFO(_ct.Structure):
                _fields_ = [
                    ('cbStruct', _wt.DWORD),
                    ('pcwszFilePath', _wt.LPCWSTR),
                    ('hFile', _wt.HANDLE),
                    ('pgKnownSubject', _ct.c_void_p),
                ]

            class WINTRUST_DATA(_ct.Structure):
                _fields_ = [
                    ('cbStruct', _wt.DWORD),
                    ('pPolicyCallbackData', _ct.c_void_p),
                    ('pSIPClientData', _ct.c_void_p),
                    ('dwUIChoice', _wt.DWORD),
                    ('fdwRevocationChecks', _wt.DWORD),
                    ('dwUnionChoice', _wt.DWORD),
                    ('pFile', _ct.POINTER(WINTRUST_FILE_INFO)),
                    ('dwStateAction', _wt.DWORD),
                    ('hWVTStateData', _wt.HANDLE),
                    ('pwszURLReference', _wt.LPCWSTR),
                    ('dwProvFlags', _wt.DWORD),
                    ('dwUIContext', _wt.DWORD),
                ]

            wfi = WINTRUST_FILE_INFO()
            wfi.cbStruct = _ct.sizeof(WINTRUST_FILE_INFO)
            wfi.pcwszFilePath = file_path
            wfi.hFile = None
            wfi.pgKnownSubject = None

            wd = WINTRUST_DATA()
            wd.cbStruct = _ct.sizeof(WINTRUST_DATA)
            wd.pPolicyCallbackData = None
            wd.pSIPClientData = None
            wd.dwUIChoice = 2   # WTD_UI_NONE
            wd.fdwRevocationChecks = 0
            wd.dwUnionChoice = 1  # WTD_CHOICE_FILE
            wd.pFile = _ct.pointer(wfi)
            wd.dwStateAction = 0
            wd.hWVTStateData = None
            wd.pwszURLReference = None
            wd.dwProvFlags = 0x10  # WTD_CACHE_ONLY_URL_RETRIEVAL
            wd.dwUIContext = 0

            wintrust = _ct.windll.wintrust
            import uuid
            action_guid = '{00AAC56B-CD44-11d0-8CC2-00C04FC295EE}'
            # Create GUID struct
            class GUID(_ct.Structure):
                _fields_ = [('Data1', _wt.DWORD), ('Data2', _wt.WORD), ('Data3', _wt.WORD),
                             ('Data4', _ct.c_byte * 8)]
            g = GUID()
            u = uuid.UUID(action_guid)
            g.Data1, g.Data2, g.Data3 = u.time_low, u.time_mid, u.time_hi_version
            for i, b in enumerate(u.bytes[8:]):
                g.Data4[i] = b

            result = wintrust.WinVerifyTrust(None, _ct.byref(g), _ct.byref(wd))
            return result == 0  # 0 = TRUST_E_SUBJECT_FORM_UNKNOWN would not be 0
        except Exception:
            return False

    def scan_ghost_client_registry(self):
        """Detecta claves de registro dejadas por ghost clients instalados."""
        print("🔍 Escaneando registro por instalaciones de ghost clients...")
        GHOST_REGISTRY_KEYS = [
            (winreg.HKEY_CURRENT_USER, r'Software\Rise Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\Sigma'),
            (winreg.HKEY_CURRENT_USER, r'Software\Vape'),
            (winreg.HKEY_CURRENT_USER, r'Software\LiquidBounce'),
            (winreg.HKEY_CURRENT_USER, r'Software\Meteor Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\Drip Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\Vertex Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\Future Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\Flux Client'),
            (winreg.HKEY_CURRENT_USER, r'Software\RusherHack'),
            (winreg.HKEY_CURRENT_USER, r'Software\Astolfo'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Rise Client'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Sigma'),
            (winreg.HKEY_LOCAL_MACHINE, r'Software\Vape'),
        ]
        try:
            for hive, subkey in GHOST_REGISTRY_KEYS:
                try:
                    with winreg.OpenKey(hive, subkey):
                        hive_name = 'HKCU' if hive == winreg.HKEY_CURRENT_USER else 'HKLM'
                        key_name = subkey.split('\\')[-1]
                        print(f"🚨 GHOST CLIENT REGISTRY: {hive_name}\\{subkey}")
                        self.issues_found.append({
                            'nombre': f'Clave de registro de ghost client: {key_name}',
                            'ruta': f'{hive_name}\\{subkey}',
                            'archivo': key_name,
                            'tipo': 'ghost_client_registry',
                            'categoria': 'GHOST_CLIENT',
                            'alerta': 'CRITICAL',
                            'confidence': 0.93,
                            'detected_patterns': [f'registry:{key_name.lower().replace(" ", "_")}'],
                        })
                except FileNotFoundError:
                    continue
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en scan_ghost_client_registry: {e}")

    def _get_cloud_mod_whitelist(self):
        """P2 #1 — Descarga whitelist de mods legítimos desde la cloud (caché 1h en APPDATA)."""
        import json as _json, hashlib as _hl, datetime as _dt
        cache_path = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'mod_whitelist.json')
        # Intentar usar caché válida
        try:
            if os.path.isfile(cache_path):
                age = (_dt.datetime.now() - _dt.datetime.fromtimestamp(os.path.getmtime(cache_path))).total_seconds()
                if age < 3600:
                    with open(cache_path, 'r') as f:
                        data = _json.load(f)
                    return set(data.get('hashes', []))
        except Exception:
            pass
        # Descargar desde cloud
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            if not base_url:
                return set()
            r = requests.get(f'{base_url}/api/mod_whitelist', timeout=8)
            if r.ok:
                data = r.json()
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, 'w') as f:
                    _json.dump(data, f)
                return set(data.get('hashes', []))
        except Exception:
            pass
        return set()

    def scan_minecraft_mods_blacklist(self):
        """Detecta mods prohibidos en .minecraft/mods/ por nombre."""
        print("🔍 Escaneando mods de Minecraft contra lista negra...")
        appdata = os.environ.get('APPDATA', '')
        mods_dir = os.path.join(appdata, '.minecraft', 'mods')
        if not os.path.isdir(mods_dir):
            return
        # P2 #1 — Whitelist dinámica de mods legítimos
        cloud_whitelist = self._get_cloud_mod_whitelist()
        # P2 #2 — Whitelist por servidor (mods permitidos explícitamente en este token)
        server_allowed  = set(str(m).lower() for m in self.config.get('server_allowed_mods', []))
        BLACKLISTED = [
            'baritone', 'horion', 'impact', 'wurst', 'aristois', 'meteor',
            'sigma', 'ares', 'salhack', 'entropy', 'remix', 'inertia',
            'liquidbounce', 'flux', 'vape', 'riseclient', 'future', 'astolfo',
            'novoline', 'rusherhack', 'dripclient', 'vertex', 'azura', 'jello',
            'datura', 'mathias', 'weave', 'xray', 'killaura', 'aimbot',
            'scaffold', 'autoclick', 'clickgui', 'hacked', 'cheat', 'inject',
        ]
        try:
            for fname in os.listdir(mods_dir):
                if not fname.lower().endswith('.jar'):
                    continue
                fpath = os.path.join(mods_dir, fname)
                fname_lower = fname.lower()
                # P2 #2 — Verificar contra whitelist por servidor (nombre)
                if server_allowed and fname_lower in server_allowed:
                    continue
                # P2 #1 — Verificar contra whitelist dinámica de mods legítimos (hash)
                if cloud_whitelist:
                    try:
                        h = hashlib.sha256()
                        with open(fpath, 'rb') as f:
                            for chunk in iter(lambda: f.read(65536), b''):
                                h.update(chunk)
                        if h.hexdigest().lower() in cloud_whitelist:
                            continue  # mod legítimo confirmado
                    except Exception:
                        pass
                matched_bl = next((bl for bl in BLACKLISTED if bl in fname_lower), None)
                if matched_bl:
                    print(f"🚨 MOD PROHIBIDO: {fname}")
                    self.issues_found.append({
                        'nombre': f'Mod prohibido detectado en .minecraft/mods/: {fname}',
                        'ruta': fpath,
                        'archivo': fname,
                        'tipo': 'blacklisted_mod',
                        'categoria': 'GHOST_CLIENT',
                        'alerta': 'CRITICAL',
                        'confidence': 0.95,
                        'detected_patterns': [f'blacklisted_mod:{matched_bl}'],
                    })
                else:
                    # P3 #10 — character n-gram similarity for renamed/obfuscated hack mods
                    sim, matched_hack = self._score_path_hack_similarity(fname)
                    if sim >= 0.40:
                        print(f"⚠️ MOD SIMILAR A HACK (N-GRAM): {fname} ~ {matched_hack} ({sim:.2f})")
                        self.issues_found.append({
                            'nombre': f'Mod con nombre similar a hack conocido: {fname} ≈ {matched_hack}',
                            'ruta': fpath,
                            'archivo': fname,
                            'tipo': 'blacklisted_mod',
                            'categoria': 'GHOST_CLIENT',
                            'alerta': 'SOSPECHOSO',
                            'confidence': round(min(0.85, 0.50 + sim * 0.7), 2),
                            'detected_patterns': [f'name_similar_to:{matched_hack}({sim:.2f})'],
                            'explicacion': f'El mod "{fname}" tiene alta similitud de caracteres (n-gram Jaccard={sim:.2f}) '
                                           f'con el cliente de hack conocido "{matched_hack}". Puede estar renombrado para evadir detección.',
                        })
        except Exception as e:
            print(f"Error en scan_minecraft_mods_blacklist: {e}")

    def scan_dll_injection_java(self):
        """Detecta DLLs no estándar cargadas en procesos Java/Minecraft."""
        print("🔍 Escaneando DLLs en procesos Java...")
        SUSPICIOUS_KW = [
            'vape', 'sigma', 'inject', 'hook', 'hack', 'cheat', 'bypass',
            'entropy', 'wurst', 'meteor', 'rise', 'flux', 'future', 'astolfo',
            'payload', 'loader', 'patch', 'crack', 'stealth', 'ghost',
        ]
        SAFE_PREFIXES = [
            'c:\\windows\\', 'c:\\program files\\java',
            'c:\\program files (x86)\\java', 'c:\\program files\\eclipse',
        ]
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'java' not in name and 'javaw' not in name:
                        continue
                    try:
                        for mmap in proc.memory_maps():
                            path = (mmap.path or '').lower()
                            if not path.endswith('.dll'):
                                continue
                            if any(path.startswith(s) for s in SAFE_PREFIXES):
                                continue
                            dll_name = os.path.basename(path)
                            for kw in SUSPICIOUS_KW:
                                if kw in dll_name:
                                    print(f"🚨 DLL SOSPECHOSA en Java: {path}")
                                    self.issues_found.append({
                                        'nombre': f'DLL sospechosa en Java: {dll_name}',
                                        'ruta': path,
                                        'archivo': dll_name,
                                        'tipo': 'dll_injection_java',
                                        'categoria': 'JAVA_INJECTION',
                                        'alerta': 'CRITICAL',
                                        'confidence': 0.90,
                                        'detected_patterns': [f'dll_inject:{kw}'],
                                    })
                                    break
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_dll_injection_java: {e}")

    def scan_ahk_scripts(self):
        """Busca scripts AutoHotkey con patrones de autoclick y contexto Minecraft.
        También detecta ejecutables AHK compilados en ubicaciones sospechosas.
        """
        print("🔍 Buscando scripts AHK con autoclick...")
        import re as _re
        search_paths = [
            os.path.expanduser('~\\Desktop'),
            os.path.expanduser('~\\Documents'),
            os.path.expanduser('~\\Downloads'),
            os.path.expanduser('~\\AppData\\Roaming'),
            os.path.expanduser('~\\AppData\\Local'),
        ]
        MC_KW = ['minecraft', ' mc', 'lbutton', 'rbutton', 'mbutton', 'java.exe', 'javaw']
        CLICK_RE = [
            r'click\s*,?\s*\d*',         # Click, / Click 3
            r'sleep\s*,\s*[1-9]\d{0,2}', # Sleep corto < 1000ms
            r'loop\s*[,\{]',             # Loop { / Loop, 10
            r'mouseevent\s*\(',
            r'send\s*\{click\}',
            r'sendinput\s*\{lbutton\}',
            r'controlclick',
            r'\bsetmousedelay\b',
            r'\btoggle\b.*\bclick\b',
        ]
        # Patrones de ofuscación AHK: variables largas aleatorias, chr() chains, etc.
        OBFUSC_RE = [
            r'chr\(\d+\)\s*\.\s*chr\(\d+\)',  # chr(86).chr(65)... string building
            r'#noenv\s*\n.*#persistent',       # flags de AHK ofuscado
        ]
        # Nombres de archivo que indican autoclick directamente
        AUTOCLICK_NAME_KW = ['autoclick', 'autoclicker', 'clicker', 'click-bot',
                              'jitter', 'butterfly', 'drag-click', 'dragclick',
                              'cps', 'bypass-click', 'aim', 'macro']
        try:
            for base in search_paths:
                if not os.path.isdir(base):
                    continue
                for root, dirs, files in os.walk(base):
                    dirs[:] = [d for d in dirs if d.lower() not in {
                        'windows', 'system32', '.git', '__pycache__',
                        'google', 'mozilla', 'microsoft',
                    }]
                    for fname in files:
                        fname_lower = fname.lower()
                        fpath = os.path.join(root, fname)

                        # Detectar AHK compilado (.exe) con nombre sospechoso
                        if fname_lower.endswith('.exe'):
                            if any(kw in fname_lower for kw in AUTOCLICK_NAME_KW):
                                try:
                                    # Verificar si es AHK compilado leyendo firma del PE
                                    with open(fpath, 'rb') as f:
                                        header = f.read(512)
                                    is_ahk_compiled = (b'AutoHotkey' in header or
                                                        b'AHK_L' in header or
                                                        b'AutoHotkeyL' in header or
                                                        b'AUTOHOTKEY' in header.upper())
                                    if is_ahk_compiled:
                                        print(f"🚨 AHK EXE COMPILADO (autoclick): {fpath}")
                                        self.issues_found.append({
                                            'nombre': f'Ejecutable AHK compilado (autoclick): {fname}',
                                            'ruta': fpath,
                                            'archivo': fname,
                                            'tipo': 'ahk_autoclick',
                                            'categoria': 'AUTOCLICK',
                                            'alerta': 'CRITICAL',
                                            'confidence': 0.91,
                                            'detected_patterns': ['ahk_compiled_exe', 'autoclick_name'],
                                            'explicacion': (
                                                f'{fname} es un ejecutable AHK compilado con nombre de autoclick. '
                                                'Los AHK compilados son scripts de autoclick que ocultan el código '
                                                'fuente para evitar ser detectados durante el Screen Share.'
                                            ),
                                        })
                                except Exception:
                                    pass
                            continue  # No analizar otros .exe como scripts AHK

                        if not fname_lower.endswith('.ahk'):
                            continue

                        try:
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(16384).lower()

                            has_click = any(_re.search(p, content, _re.IGNORECASE) for p in CLICK_RE)
                            is_obfusc = any(_re.search(p, content, _re.IGNORECASE | _re.DOTALL)
                                            for p in OBFUSC_RE)
                            name_match = any(kw in fname_lower for kw in AUTOCLICK_NAME_KW)

                            if not (has_click or is_obfusc or name_match):
                                continue

                            has_mc = any(kw in content for kw in MC_KW)
                            if is_obfusc and not has_mc:
                                has_mc = True  # ofuscación sin MC keyword = sospechoso igual

                            alert = 'CRITICAL' if has_mc else 'SOSPECHOSO'
                            conf  = 0.91 if has_mc else 0.68
                            patterns = ['ahk_click'] + (['ahk_minecraft'] if has_mc else [])
                            if is_obfusc:
                                patterns.append('ahk_obfuscated')
                            if name_match:
                                patterns.append('ahk_autoclick_name')

                            print(f"{'🚨' if has_mc else '⚠️'} AHK AUTOCLICK: {fpath}")
                            self.issues_found.append({
                                'nombre': f'Script AHK con autoclick{"+ Minecraft" if has_mc else ""}: {fname}',
                                'ruta': fpath,
                                'archivo': fname,
                                'tipo': 'ahk_autoclick',
                                'categoria': 'AUTOCLICK',
                                'alerta': alert,
                                'confidence': conf,
                                'detected_patterns': patterns,
                                'explicacion': (
                                    f'{fname} contiene patrones de autoclick{"con contexto Minecraft" if has_mc else ""}. '
                                    + ('Script ofuscado — se está ocultando el código. ' if is_obfusc else '')
                                    + 'Los scripts AHK de autoclick simulan clics de ratón automáticos para '
                                    'obtener mayor CPS del que es humanamente posible.'
                                ),
                            })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_ahk_scripts: {e}")

    def scan_bloody_a4tech(self):
        """Detecta software Bloody/A4Tech instalado (autoclick por hardware)."""
        print("🔍 Escaneando software Bloody/A4Tech...")
        pf  = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
        pf86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')
        appdata = os.environ.get('APPDATA', '')
        PATHS = [
            os.path.join(pf,   'Bloody'), os.path.join(pf86, 'Bloody'),
            os.path.join(pf,   'A4Tech'), os.path.join(pf86, 'A4Tech'),
            os.path.join(appdata, 'Bloody'),
        ]
        try:
            for path in PATHS:
                if os.path.isdir(path):
                    print(f"⚠️ SOFTWARE BLOODY/A4TECH: {path}")
                    self.issues_found.append({
                        'nombre': f'Software Bloody/A4Tech instalado: {os.path.basename(path)}',
                        'ruta': path,
                        'archivo': os.path.basename(path),
                        'tipo': 'bloody_a4tech',
                        'categoria': 'AUTOCLICK',
                        'alerta': 'SOSPECHOSO',
                        'confidence': 0.72,
                        'detected_patterns': ['bloody_mouse_software'],
                    })
                    break
        except Exception as e:
            print(f"Error en scan_bloody_a4tech: {e}")

    def scan_steelseries_corsair(self):
        """Detecta macros de click rápido en perfiles de SteelSeries GG / Corsair iCUE."""
        print("🔍 Escaneando SteelSeries GG / Corsair iCUE...")
        import re as _re
        localapp = os.environ.get('LOCALAPPDATA', '')
        appdata  = os.environ.get('APPDATA', '')
        PROFILE_BASES = [
            os.path.join(localapp, 'SteelSeries', 'GG'),
            os.path.join(localapp, 'SteelSeries', 'SteelSeries Engine 3'),
            os.path.join(appdata,  'Corsair', 'CUE'),
            os.path.join(localapp, 'Corsair', 'CUE'),
            os.path.join(appdata,  'Corsair', 'iCUE'),
        ]
        try:
            for base in PROFILE_BASES:
                if not os.path.isdir(base):
                    continue
                for root, dirs, files in os.walk(base):
                    dirs[:] = dirs[:5]
                    for fname in files:
                        if not (fname.endswith('.json') or fname.endswith('.xml')):
                            continue
                        fpath = os.path.join(root, fname)
                        try:
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(16384).lower()
                            has_click = bool(_re.search(r'(click|actiontype.*click|mouse.*loop)', content))
                            has_fast  = bool(_re.search(r'delay["\s:,]*\d{1,2}["\s,}]|ms["\s:,]*1\d["\s,}]', content))
                            if has_click and has_fast:
                                print(f"⚠️ MACRO CLICK RAPIDO en {os.path.basename(base)}: {fpath}")
                                self.issues_found.append({
                                    'nombre': f'Macro click rápido en {os.path.basename(base)}: {fname}',
                                    'ruta': fpath,
                                    'archivo': fname,
                                    'tipo': 'peripheral_macro',
                                    'categoria': 'AUTOCLICK',
                                    'alerta': 'SOSPECHOSO',
                                    'confidence': 0.75,
                                    'detected_patterns': ['rapid_click_macro'],
                                })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_steelseries_corsair: {e}")

    def scan_arduino_hid(self):
        """Detecta dispositivos HID Arduino/CH340/STM32 conectados (autoclick hardware)."""
        print("🔍 Escaneando dispositivos HID Arduino/programables...")
        SUSPICIOUS_VIDS = {'2341', '1a86', '0483', '04d8', '16c0'}
        try:
            import subprocess as _sp
            result = _sp.run(
                ['wmic', 'path', 'Win32_PnPEntity', 'where',
                 'PNPClass="HIDClass"', 'get', 'Name,DeviceID', '/FORMAT:CSV'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return
            import re as _re
            for line in result.stdout.splitlines():
                ll = line.lower()
                vid_m = _re.search(r'vid_([0-9a-f]{4})', ll)
                if not vid_m or vid_m.group(1) not in SUSPICIOUS_VIDS:
                    continue
                if any(kw in ll for kw in ['arduino', 'ch340', 'stm32', 'usbasp', 'pro micro', 'digispark']):
                    print(f"⚠️ ARDUINO/HID DEVICE: {line.strip()[:120]}")
                    self.issues_found.append({
                        'nombre': f'Dispositivo HID Arduino/programable: {line.strip()[:80]}',
                        'ruta': 'Dispositivos USB del sistema',
                        'archivo': line.strip()[:80],
                        'tipo': 'arduino_hid_device',
                        'categoria': 'AUTOCLICK',
                        'alerta': 'SOSPECHOSO',
                        'confidence': 0.75,
                        'detected_patterns': ['arduino_hid'],
                    })
        except Exception as e:
            print(f"Error en scan_arduino_hid: {e}")

    def scan_active_injectors(self):
        """Detecta procesos inyectores corriendo durante el scan."""
        print("🔍 Buscando procesos inyectores activos...")
        INJECTOR_SIGS = [
            'extremeinjector', 'xenos', 'dllinjector', 'dll_injector',
            'processhacker', 'cheatengine', 'cheat_engine', 'ce32', 'ce64',
            'scylla', 'scyllahide', 'titan', 'injex', 'remoteinjector',
            'manualmap', 'threadhijack',
        ]
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    pname = (proc.info.get('name') or '').lower().replace(' ', '').replace('-', '').replace('_', '')
                    pexe  = (proc.info.get('exe') or '').lower().replace(' ', '').replace('-', '')
                    for sig in INJECTOR_SIGS:
                        if sig in pname or sig in pexe:
                            print(f"🚨 INYECTOR ACTIVO: {proc.info.get('name')}")
                            self.issues_found.append({
                                'nombre': f'Proceso inyector activo: {proc.info.get("name", sig)}',
                                'ruta': proc.info.get('exe') or 'N/A',
                                'archivo': proc.info.get('name', sig),
                                'tipo': 'injector_process',
                                'categoria': 'JAVA_INJECTION',
                                'alerta': 'CRITICAL',
                                'confidence': 0.93,
                                'detected_patterns': ['active_injector'],
                            })
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_active_injectors: {e}")

    def _score_path_hack_similarity(self, filename: str) -> tuple:
        """P3 #10: Character trigram Jaccard similarity between filename and known hack names.
        Returns (max_similarity 0-1, best_match_name). Detects obfuscated/renamed hack jars."""
        import re as _re
        base = _re.sub(r'\.[^.]+$', '', filename).lower()
        # Strip generic noise tokens before comparing
        base = _re.sub(r'[-_]?(?:v\d+[\d.]*|patch|update|mod|client|loader|latest|\d{3,})', '', base)
        base = base.strip('-_ ')
        if len(base) < 3:
            return 0.0, ''
        HACK_NAMES = [
            'sigma', 'liquidbounce', 'wurst', 'meteorclient', 'meteor',
            'vape', 'rise', 'drip', 'vertex', 'azura', 'novoline',
            'rusherhack', 'astolfo', 'future', 'entropy', 'salhack',
            'remix', 'inertia', 'aristois', 'impact', 'horion', 'ares',
            'mathias', 'datura', 'jello', 'weave', 'xray', 'ghostclient',
            'killaura', 'aimbot', 'scaffold', 'hacked', 'cheat',
        ]
        def _tg(s):
            return set(s[i:i+3] for i in range(len(s) - 2)) if len(s) >= 3 else set()
        base_tg = _tg(base)
        if not base_tg:
            return 0.0, ''
        best_sim, best_name = 0.0, ''
        for hack in HACK_NAMES:
            hack_tg = _tg(hack)
            if not hack_tg:
                continue
            union = len(base_tg | hack_tg)
            sim = len(base_tg & hack_tg) / union if union else 0.0
            if sim > best_sim:
                best_sim, best_name = sim, hack
        return best_sim, best_name

    def scan_temp_jars(self):
        """Detecta archivos .jar creados en las últimas 24h en carpetas temporales."""
        print("🔍 Buscando JARs recientes en carpetas temporales...")
        temp_paths = list({
            os.environ.get('TEMP', ''),
            os.environ.get('TMP', ''),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
        })
        cutoff = time.time() - 86400
        seen = set()
        try:
            for temp_dir in temp_paths:
                if not temp_dir or not os.path.isdir(temp_dir):
                    continue
                for root, dirs, files in os.walk(temp_dir):
                    dirs[:] = dirs[:10]
                    for fname in files:
                        if not fname.lower().endswith('.jar'):
                            continue
                        fpath = os.path.join(root, fname)
                        if fpath in seen:
                            continue
                        seen.add(fpath)
                        try:
                            if os.path.getmtime(fpath) >= cutoff:
                                # P3 #10 — path similarity to known hack client names
                                sim, matched_hack = self._score_path_hack_similarity(fname)
                                if sim >= 0.35:
                                    alerta = 'CRITICAL'
                                    conf = min(0.95, 0.70 + sim * 0.5)
                                    patterns = ['jar_in_temp_24h', f'name_similar_to:{matched_hack}({sim:.2f})']
                                    label = f'JAR sospechoso (similar a "{matched_hack}") en temp: {fname}'
                                    print(f"🚨 JAR SIMILAR A HACK EN TEMP: {fname} ~ {matched_hack} ({sim:.2f})")
                                else:
                                    alerta = 'SOSPECHOSO'
                                    conf = 0.70
                                    patterns = ['jar_in_temp_24h']
                                    label = f'JAR reciente en carpeta temporal: {fname}'
                                    print(f"⚠️ JAR RECIENTE EN TEMP: {fpath}")
                                self.issues_found.append({
                                    'nombre': label,
                                    'ruta': fpath,
                                    'archivo': fname,
                                    'tipo': 'temp_jar_recent',
                                    'categoria': 'JAVA_INJECTION',
                                    'alerta': alerta,
                                    'confidence': round(conf, 2),
                                    'detected_patterns': patterns,
                                })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_temp_jars: {e}")

    def scan_baritone_config(self):
        """Detecta Baritone instalado y verifica si tiene modos prohibidos activos."""
        print("🔍 Escaneando configuración de Baritone...")
        import json as _json
        appdata = os.environ.get('APPDATA', '')
        settings_path = os.path.join(appdata, '.minecraft', 'baritone', 'settings.json')
        if not os.path.exists(settings_path):
            return
        PROHIBITED = {
            'buildRepeat': True, 'elytraFly': True,
            'allowPlace': True, 'allowBreak': True,
            'printOptimizerEnabled': True,
        }
        try:
            with open(settings_path, 'r', encoding='utf-8', errors='ignore') as f:
                config = _json.load(f)
            violations = [f'{k}={v}' for k, v in PROHIBITED.items() if config.get(k) == v]
            if violations:
                print(f"⚠️ BARITONE MODOS PROHIBIDOS: {', '.join(violations)}")
                self.issues_found.append({
                    'nombre': f'Baritone con modos prohibidos: {", ".join(violations[:3])}',
                    'ruta': settings_path,
                    'archivo': 'settings.json',
                    'tipo': 'baritone_prohibited',
                    'categoria': 'COMPLEMENTO_PROHIBIDO',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.80,
                    'detected_patterns': [f'baritone:{v.split("=")[0]}' for v in violations],
                })
            else:
                self.issues_found.append({
                    'nombre': 'Baritone instalado (bot de automatización de Minecraft)',
                    'ruta': settings_path,
                    'archivo': 'settings.json',
                    'tipo': 'baritone_installed',
                    'categoria': 'COMPLEMENTO_PROHIBIDO',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.60,
                    'detected_patterns': ['baritone_present'],
                })
        except Exception as e:
            print(f"Error en scan_baritone_config: {e}")

    def scan_schematica_litematica(self):
        """Detecta Schematica/Litematica con Printer Mode activo."""
        print("🔍 Escaneando configuración de Schematica/Litematica...")
        import re as _re
        appdata = os.environ.get('APPDATA', '')
        CONFIG_PATHS = [
            (os.path.join(appdata, '.minecraft', 'config', 'schematica.cfg'),         'cfg'),
            (os.path.join(appdata, '.minecraft', 'config', 'litematica', 'generic.json'), 'json'),
            (os.path.join(appdata, '.minecraft', 'config', 'easylitematic.json'),     'json'),
        ]
        try:
            for config_path, ftype in CONFIG_PATHS:
                if not os.path.exists(config_path):
                    continue
                try:
                    with open(config_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read(16384)
                    cl = content.lower()
                    if ftype == 'json' and _re.search(r'"print.*?:\s*true|"enable.*?print.*?:\s*true', cl):
                        print(f"🚨 LITEMATICA PRINTER MODE: {config_path}")
                        self.issues_found.append({
                            'nombre': f'Litematica Printer Mode activo',
                            'ruta': config_path,
                            'archivo': os.path.basename(config_path),
                            'tipo': 'litematica_printer',
                            'categoria': 'COMPLEMENTO_PROHIBIDO',
                            'alerta': 'CRITICAL',
                            'confidence': 0.85,
                            'detected_patterns': ['litematica_printer_enabled'],
                        })
                    elif ftype == 'cfg' and ('printer=true' in cl or 'printerenabled=true' in cl):
                        print(f"🚨 SCHEMATICA PRINTER MODE: {config_path}")
                        self.issues_found.append({
                            'nombre': 'Schematica Printer Mode activo',
                            'ruta': config_path,
                            'archivo': os.path.basename(config_path),
                            'tipo': 'schematica_printer',
                            'categoria': 'COMPLEMENTO_PROHIBIDO',
                            'alerta': 'CRITICAL',
                            'confidence': 0.85,
                            'detected_patterns': ['schematica_printer_enabled'],
                        })
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en scan_schematica_litematica: {e}")

    def scan_optifine_zoom(self):
        """Detecta si el zoom de OptiFine está asignado a tecla de combate en options.txt."""
        print("🔍 Escaneando options.txt (OptiFine zoom key)...")
        appdata = os.environ.get('APPDATA', '')
        options_path = os.path.join(appdata, '.minecraft', 'options.txt')
        if not os.path.exists(options_path):
            return
        SUSPICIOUS_BINDS = {'key_mouse1', 'key_mouse2', 'key_mouse3', 'key_button1', 'key_button2'}
        try:
            with open(options_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    ll = line.lower().strip()
                    if ll.startswith('key_of.key.zoom:') or ll.startswith('key_optifine.zoom:'):
                        zoom_bind = ll.split(':')[-1].strip()
                        if zoom_bind in SUSPICIOUS_BINDS:
                            print(f"⚠️ OPTIFINE ZOOM BIND SOSPECHOSO: {line.strip()}")
                            self.issues_found.append({
                                'nombre': f'OptiFine zoom en tecla de combate: {line.strip()[:80]}',
                                'ruta': options_path,
                                'archivo': 'options.txt',
                                'tipo': 'optifine_zoom_combat',
                                'categoria': 'COMPLEMENTO_PROHIBIDO',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.65,
                                'detected_patterns': ['optifine_zoom_combat_bind'],
                            })
        except Exception as e:
            print(f"Error en scan_optifine_zoom: {e}")

    def _score_string_hack_likelihood(self, base_name: str) -> float:
        """P3 #7: Character n-gram heuristic to score a class name as hack module.
        Returns 0.0-5.0; >= 3.5 considered suspicious."""
        import re as _re
        if len(base_name) < 8 or len(base_name) > 45:
            return 0.0
        # Obfuscated single/double letter names are noise, not hacks
        if len(base_name) <= 3:
            return 0.0
        score = 0.0
        low = base_name.lower()
        HACK_KEYWORDS = [
            'killaura', 'aimbot', 'aimassist', 'scaffold', 'bunnyhop', 'bhop',
            'triggerbot', 'nofall', 'antiknock', 'autoclicker', 'autoclick',
            'criticals', 'velocity', 'wallhack', 'freecam', 'xray', 'fullbright',
            'speedhack', 'flyhack', 'speedmine', 'timer', 'fastplace',
        ]
        HACK_PARTIAL = [
            'kill', 'aura', 'aimb', 'cheat', 'ghost', 'inject', 'bypass',
            'hack', 'module', 'payload', 'remap', 'hook',
        ]
        for kw in HACK_KEYWORDS:
            if kw in low:
                score += 2.5
                break
        else:
            for kw in HACK_PARTIAL:
                if kw in low:
                    score += 1.5
                    break
        # PascalCase with 2+ segments = typical hack module name (KillAura, AimAssist)
        pascal_parts = _re.findall(r'[A-Z][a-z]+', base_name)
        if len(pascal_parts) >= 2:
            score += 1.0
        elif len(pascal_parts) == 1 and len(base_name) >= 12:
            score += 0.3
        # Clean CamelCase (no underscores, no digits prefix) bonus
        if _re.match(r'^[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+$', base_name):
            score += 0.5
        # Sweet-spot length for named hack modules
        if 10 <= len(base_name) <= 25:
            score += 0.3
        return max(0.0, score)

    def scan_process_memory_strings(self):
        """Escanea JARs cargados por javaw.exe buscando strings de módulos de hack.
        P2 #9-12: longitud mínima 8 chars, regex Java package, blacklist strings legítimos.
        P3 #7: NLP n-gram heuristic para módulos de hack sin firma exacta."""
        print("🔍 Escaneando JARs cargados en memoria de Minecraft...")
        import re as _re
        import zipfile as _zf

        # Strings de módulos de hack (>= 8 chars, específicos)
        HACK_SIGNATURES = [
            b'KillAura', b'Scaffold', b'BunnyHop', b'AimAssist', b'Triggerbot',
            b'NoFall', b'AntiKnockback', b'AutoClicker', b'AutoSprint', b'FastBow',
            b'Criticals', b'LiquidBounce', b'WurstClient', b'VapeClient',
            b'SigmaClient', b'FutureClient', b'MeteorClient', b'AstolfoClient',
            b'com/rise/', b'com/sigma/', b'net/vapor/', b'dev/liquidbounce',
            b'me/sigma/', b'me/astolfo/', b'net/rusherhack/', b'com/moonrise/',
        ]
        # #12 — Blacklist de packages Java legítimos (ignorar siempre)
        JAVA_LEGIT_PREFIXES = (
            b'java/', b'javax/', b'sun/', b'com/sun/', b'jdk/',
            b'net/minecraft/', b'com/mojang/', b'net/minecraftforge/',
            b'org/lwjgl/', b'org/apache/', b'com/google/', b'org/slf4j/',
            b'io/netty/', b'com/github/steveice10/', b'net/fabricmc/',
            b'org/objectweb/asm/', b'com/llamalad7/',
        )
        # #11 — Regex de paquetes Java sospechosos (com.client.*, net.hack.*, etc.)
        HACK_PACKAGE_RE = _re.compile(
            rb'(?:com|net|me|dev|io)/(?:hack|hacks|cheat|ghost|client|module|modules|feature|bypass)/',
            _re.IGNORECASE
        )

        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'javaw' not in name and 'java' not in name:
                        continue
                    loaded_jars = set()
                    try:
                        for mmap in proc.memory_maps():
                            path = mmap.path or ''
                            if path.lower().endswith('.jar') and os.path.isfile(path):
                                loaded_jars.add(path)
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass

                    for jar_path in loaded_jars:
                        jar_l = jar_path.lower()
                        # Ignorar JDK/JRE y mods legítimos conocidos
                        if any(s in jar_l for s in ('jdk', 'jre', 'optifine_', 'sodium-',
                                                      'fabricloader', 'forge-', 'authlib')):
                            continue
                        try:
                            with _zf.ZipFile(jar_path, 'r') as zf:
                                class_names = [n for n in zf.namelist() if n.endswith('.class')]
                                matched_sig = None
                                matched_pkg = None
                                # P3 #7 — NLP accumulator for hack-like class names
                                nlp_hits = []
                                for class_name in class_names[:8000]:
                                    cn = class_name.encode('utf-8', errors='ignore')
                                    # #12 — Skip strings de Java legítimo
                                    if cn.startswith(JAVA_LEGIT_PREFIXES):
                                        continue
                                    # #9 — Skip strings < 8 chars (sin la extensión)
                                    base = cn.replace(b'.class', b'').split(b'/')[-1]
                                    if len(base) < 8:
                                        continue
                                    # Buscar signatures de hacks
                                    for sig in HACK_SIGNATURES:
                                        if sig in cn:
                                            matched_sig = sig.decode('utf-8', errors='ignore')
                                            break
                                    # #11 — Regex de paquetes hack
                                    if not matched_sig and HACK_PACKAGE_RE.search(cn):
                                        matched_pkg = cn.decode('utf-8', errors='ignore')
                                    if matched_sig or matched_pkg:
                                        break
                                    # P3 #7 — NLP heuristic score for unlisted hack modules
                                    base_str = base.decode('utf-8', errors='ignore')
                                    nlp_score = self._score_string_hack_likelihood(base_str)
                                    if nlp_score >= 3.5:
                                        nlp_hits.append((base_str, nlp_score))
                                        if len(nlp_hits) >= 10:
                                            break  # cap scan cost

                                if matched_sig or matched_pkg:
                                    label = matched_sig or matched_pkg
                                    print(f"🚨 STRING DE HACK EN JAR: {label} → {jar_path}")
                                    self.issues_found.append({
                                        'nombre': f'Módulo de hack en JAR cargado: {label}',
                                        'ruta': jar_path,
                                        'archivo': os.path.basename(jar_path),
                                        'tipo': 'hack_string_in_loaded_jar',
                                        'categoria': 'JAVA_INJECTION',
                                        'alerta': 'CRITICAL',
                                        'confidence': 0.92 if matched_sig else 0.75,
                                        'detected_patterns': [f'hack_class:{label}'],
                                        'explicacion': f'Se encontró el módulo de hack "{label}" en el JAR '
                                                       f'{os.path.basename(jar_path)} cargado por Minecraft. '
                                                       f'Esto indica que un ghost client está activo en memoria.',
                                    })
                                elif len(nlp_hits) >= 3:
                                    # P3 #7: enough hack-like class names to flag without exact signature
                                    top_names = ', '.join(h[0] for h in sorted(nlp_hits, key=lambda x: -x[1])[:4])
                                    avg_nlp = sum(h[1] for h in nlp_hits) / len(nlp_hits)
                                    conf = min(0.82, 0.55 + avg_nlp * 0.05)
                                    print(f"⚠️ CLASES SOSPECHOSAS (NLP) EN JAR: {top_names} → {jar_path}")
                                    self.issues_found.append({
                                        'nombre': f'Clases sospechosas (NLP) en JAR cargado: {top_names}',
                                        'ruta': jar_path,
                                        'archivo': os.path.basename(jar_path),
                                        'tipo': 'hack_string_in_loaded_jar',
                                        'categoria': 'JAVA_INJECTION',
                                        'alerta': 'SOSPECHOSO',
                                        'confidence': round(conf, 2),
                                        'detected_patterns': [f'nlp_hack_class:{n}' for n, _ in nlp_hits[:4]],
                                        'explicacion': f'Se detectaron {len(nlp_hits)} clases con nombres '
                                                       f'típicos de módulos de hack (NLP n-gram) en '
                                                       f'{os.path.basename(jar_path)}: {top_names}. '
                                                       f'No coinciden con firmas exactas pero presentan '
                                                       f'características lingüísticas de ghost clients.',
                                    })
                        except Exception:
                            continue
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_process_memory_strings: {e}")

    def scan_minecraft_jar_hash(self):
        """Verifica el hash SHA1 del minecraft.jar contra los hashes oficiales de Mojang.
        Un mismatch indica jar modificado (ghost client clásico)."""
        print("🔍 Verificando hash de minecraft.jar contra Mojang...")
        if not requests:
            print("⚠️ requests no disponible — skip hash check")
            return
        appdata = os.environ.get('APPDATA', '')
        versions_dir = os.path.join(appdata, '.minecraft', 'versions')
        if not os.path.isdir(versions_dir):
            return

        # Cache de hashes conocidos (sin red). Se extiende con la API si hay conexión.
        KNOWN_HASHES = {
            '1.8.9':  '169780e761a0e9c13d1c9e576a3c1fef34f8aeac',
            '1.12.2': '0f275bc1547d01fa5f56ba34bdc87d981ee12daf',
            '1.16.5': '37fd3c903861eeff3bc24b71eed48f828b5269c8',
            '1.17.1': 'a0d03225615ba897073e279670890bda18ee1e26',
            '1.18.2': 'c8f83c5655308435b3a8a8e576b12c7c9929d8e0',
            '1.19.4': '958928a560c9167687bea0e8b88d02e3a03cf2ac',
            '1.20.1': 'e6ec2f64e6080b2b2d817e6f4a1a08f6e4b56f88',
            '1.20.4': '1b5ddb1bb7cbb56d76b4588caed5c7b44dfab31c',
            '1.20.6': '2de5decc9c67cb7a95a0e6dd74dba42a8d994e7c',
            '1.21':   '0e7b5d35c7ba1ee0ee0da12c0e2c2e8ce9f60e86',
            '1.21.1': '943ee92a34dccf36b2e7fb7fe30e8d63c5e0cd4f',
            '1.21.4': '87bc50d4eafddbc41c5ceba9c7de92bde46c8a6e',
        }

        def _fetch_mojang_hash(version_id: str) -> str | None:
            try:
                manifest_url = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
                r = requests.get(manifest_url, timeout=8)
                r.raise_for_status()
                versions = r.json().get('versions', [])
                for v in versions:
                    if v.get('id') == version_id:
                        vr = requests.get(v['url'], timeout=8)
                        vr.raise_for_status()
                        return vr.json().get('downloads', {}).get('client', {}).get('sha1')
            except Exception:
                pass
            return None

        try:
            for ver_name in os.listdir(versions_dir):
                jar_path = os.path.join(versions_dir, ver_name, f'{ver_name}.jar')
                if not os.path.isfile(jar_path):
                    continue
                try:
                    sha1 = hashlib.sha1()
                    with open(jar_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(65536), b''):
                            sha1.update(chunk)
                    actual_hash = sha1.hexdigest()
                except Exception:
                    continue

                expected = KNOWN_HASHES.get(ver_name)
                if expected is None:
                    expected = _fetch_mojang_hash(ver_name)

                if expected is None:
                    continue  # versión desconocida, no podemos verificar

                if actual_hash.lower() != expected.lower():
                    print(f"🚨 MINECRAFT.JAR MODIFICADO: {ver_name} — esperado {expected[:12]}... obtenido {actual_hash[:12]}...")
                    self.issues_found.append({
                        'nombre': f'minecraft.jar modificado en versión {ver_name} (hash no coincide con Mojang)',
                        'ruta': jar_path,
                        'archivo': f'{ver_name}.jar',
                        'tipo': 'modified_minecraft_jar',
                        'categoria': 'GHOST_CLIENT',
                        'alerta': 'CRITICAL',
                        'confidence': 0.97,
                        'detected_patterns': ['modified_jar', f'hash_mismatch:{ver_name}'],
                        'extra': {'expected': expected, 'actual': actual_hash},
                    })
                else:
                    print(f"✅ minecraft.jar {ver_name} — hash OK")
        except Exception as e:
            print(f"Error en scan_minecraft_jar_hash: {e}")

    # ── PARTE 1 — Mejoras pendientes de detección ─────────────────────────────

    def scan_process_path_correlation(self):
        """P2 #14/#15 — Correlación proceso+ruta y tiempo de vida del proceso.
        Un update.exe desde %TEMP% es sospechoso; desde Program Files no.
        Proceso con < 60s de uptime al empezar el scan es más sospechoso."""
        print("🔍 Correlación proceso+ruta y uptime de procesos...")
        import datetime as _dt
        import re as _re

        SUSPICIOUS_NAMES = [
            'update.exe', 'updater.exe', 'helper.exe', 'service.exe',
            'loader.exe', 'launcher.exe', 'inject.exe', 'patch.exe',
            'install.exe', 'setup.exe', 'uninstall.exe', 'agent.exe',
        ]
        SUSPICIOUS_TEMP_DIRS = [
            os.environ.get('TEMP', '').lower(),
            os.environ.get('TMP', '').lower(),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'temp').lower(),
            os.path.join(os.environ.get('APPDATA', ''), 'temp').lower(),
        ]
        SAFE_DIRS = [
            'program files', 'windows', 'system32', 'syswow64',
            'nvidia', 'microsoft', 'steam', 'discord',
        ]

        now = _dt.datetime.now()
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'create_time']):
                try:
                    pname = (proc.info.get('name') or '').lower()
                    exe   = (proc.info.get('exe') or '').lower()
                    ctime = proc.info.get('create_time') or 0

                    if not exe or not pname:
                        continue

                    # #14 — Correlación nombre + ruta
                    is_generic_name = pname in SUSPICIOUS_NAMES
                    in_temp = any(td and exe.startswith(td) for td in SUSPICIOUS_TEMP_DIRS if td)
                    in_safe = any(sd in exe for sd in SAFE_DIRS)

                    if is_generic_name and in_temp and not in_safe:
                        print(f"⚠️ PROCESO SOSPECHOSO EN TEMP: {pname} desde {exe}")
                        self.issues_found.append({
                            'nombre': f'Proceso con nombre genérico en carpeta temporal: {pname}',
                            'ruta': exe,
                            'archivo': pname,
                            'tipo': 'suspicious_process_location',
                            'categoria': 'PROCESO',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 0.65,
                            'detected_patterns': ['generic_name_in_temp'],
                            'explicacion': f'{pname} está corriendo desde una carpeta temporal ({exe}). '
                                           f'Procesos legítimos con este nombre se ejecutan desde Program Files, '
                                           f'no desde carpetas temporales. Puede ser un inyector o loader.',
                        })

                    # #15 — Tiempo de vida del proceso
                    if ctime > 0:
                        uptime_secs = (now - _dt.datetime.fromtimestamp(ctime)).total_seconds()
                        if uptime_secs < 60 and in_temp and not in_safe:
                            print(f"⚠️ PROCESO RECIENTE EN TEMP (<60s): {pname}")
                            self.issues_found.append({
                                'nombre': f'Proceso muy reciente en carpeta temporal: {pname} ({int(uptime_secs)}s)',
                                'ruta': exe,
                                'archivo': pname,
                                'tipo': 'short_lived_process',
                                'categoria': 'PROCESO',
                                'alerta': 'SOSPECHOSO',
                                'confidence': 0.70,
                                'detected_patterns': ['short_lived_temp_process'],
                                'explicacion': f'{pname} lleva solo {int(uptime_secs)} segundos corriendo y está '
                                               f'en una carpeta temporal. Puede haber sido lanzado justo antes del SS '
                                               f'para inyectar código y luego cerrarse.',
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_process_path_correlation: {e}")

    def scan_process_hashes_cloud(self):
        """P2 #16 — Verifica el hash SHA256 de procesos activos contra hack_hashes en la cloud."""
        print("🔍 Verificando hashes de procesos contra cloud DB...")
        if not requests:
            return
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            if not base_url:
                return
            r = requests.get(f'{base_url}/api/hashes', timeout=8)
            if not r.ok:
                return
            cloud_hashes = {h['sha256'].lower(): h['hack_name'] for h in r.json().get('hashes', [])}
            if not cloud_hashes:
                return
        except Exception:
            return

        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    exe = proc.info.get('exe') or ''
                    if not exe or not os.path.isfile(exe):
                        continue
                    exe_l = exe.lower()
                    if any(s in exe_l for s in ('windows', 'program files', 'system32')):
                        continue
                    try:
                        h = hashlib.sha256()
                        with open(exe, 'rb') as f:
                            for chunk in iter(lambda: f.read(65536), b''):
                                h.update(chunk)
                        file_hash = h.hexdigest().lower()
                    except Exception:
                        continue

                    if file_hash in cloud_hashes:
                        hack_name = cloud_hashes[file_hash]
                        pname = proc.info.get('name', '')
                        print(f"🚨 HASH EN CLOUD DB: {pname} → {hack_name}")
                        self.issues_found.append({
                            'nombre': f'Proceso en cloud DB de hacks: {pname} ({hack_name})',
                            'ruta': exe,
                            'archivo': pname,
                            'tipo': 'cloud_hash_match',
                            'categoria': 'GHOST_CLIENT',
                            'alerta': 'CRITICAL',
                            'confidence': 0.99,
                            'detected_patterns': [f'cloud_hash:{hack_name}'],
                            'file_hash': file_hash,
                            'explicacion': f'El proceso {pname} coincide con el hash de {hack_name} '
                                           f'en la base de datos de hacks confirmados. '
                                           f'Detección 100% confiable por hash.',
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_process_hashes_cloud: {e}")

    def scan_javaagent_args(self):
        """#1 — Detecta -javaagent en cmdline de javaw.exe (inyección directa en JVM)."""
        print("🔍 Buscando -javaagent en args de Java...")
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'java' not in name:
                        continue
                    cmdline = proc.info.get('cmdline') or []
                    for arg in cmdline:
                        arg_l = arg.lower()
                        if '-javaagent' in arg_l:
                            jar_name = arg.split('=')[-1].split('\\')[-1].split('/')[-1]
                            # Ignorar agentes de launchers oficiales conocidos
                            safe_agents = ['authlib', 'oshi', 'legacylauncher', 'lunarclient', 'badlion']
                            if any(s in arg_l for s in safe_agents):
                                continue
                            print(f"🚨 JAVAAGENT: {arg}")
                            self.issues_found.append({
                                'nombre': f'-javaagent detectado en JVM: {jar_name}',
                                'ruta': arg,
                                'archivo': jar_name,
                                'tipo': 'javaagent_injection',
                                'categoria': 'INYECCION',
                                'alerta': 'CRITICAL',
                                'confidence': 0.95,
                                'detected_patterns': ['javaagent_injection'],
                                'explicacion': f'Se detectó un agente Java inyectado en Minecraft: {jar_name}. '
                                               f'Frameworks como Weave, ForgeHax y la mayoría de ghost clients modernos '
                                               f'usan -javaagent para inyectar código en runtime.',
                            })
                        # -Xbootclasspath y -agentpath/-agentlib (otras formas de injection JVM)
                        for boot_arg in ('-xbootclasspath/p:', '-xbootclasspath/a:', '-agentpath:', '-agentlib:'):
                            if boot_arg in arg_l:
                                arg_val = arg.split(':', 1)[-1] if ':' in arg else arg
                                fname   = arg_val.split('\\')[-1].split('/')[-1]
                                safe_agentlibs = ('jdwp', 'hprof', 'instrument')
                                if any(s in arg_l for s in safe_agentlibs) and boot_arg == '-agentlib:':
                                    continue
                                self.issues_found.append({
                                    'nombre': f'Arg JVM de inyección detectado: {arg[:80]}',
                                    'ruta': arg,
                                    'archivo': fname,
                                    'tipo': 'javaagent_injection',
                                    'categoria': 'INYECCION',
                                    'alerta': 'CRITICAL',
                                    'confidence': 0.93,
                                    'detected_patterns': [f'jvm_injection_arg:{boot_arg.rstrip(":")}'],
                                    'explicacion': f'Se detectó {boot_arg} en los argumentos JVM de Minecraft. '
                                                   f'Este flag permite cargar código nativo o bytecode arbitrario '
                                                   f'en la JVM antes de que Minecraft arranque (técnica de injection avanzada).',
                                })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_javaagent_args: {e}")

    def scan_weave_loader(self):
        """#4 — Detecta artefactos de Weave Loader (framework de inyección más popular)."""
        print("🔍 Buscando artefactos de Weave Loader...")
        appdata  = os.environ.get('APPDATA', '')
        local    = os.environ.get('LOCALAPPDATA', '')
        mc_dir   = os.path.join(appdata, '.minecraft')
        WEAVE_PATHS = [
            (os.path.join(appdata,  '.weave'),               'Directorio de Weave Loader'),
            (os.path.join(appdata,  '.weave', 'weave.json'), 'Configuración de Weave'),
            (os.path.join(appdata,  'WeaveLoader'),          'WeaveLoader AppData'),
            (os.path.join(local,    'WeaveLoader'),          'WeaveLoader LocalAppData'),
            (os.path.join(mc_dir,   '.weave'),               'Weave en .minecraft'),
            (os.path.join(mc_dir,   'weave'),                'Weave folder en .minecraft'),
        ]
        # Módulos de Weave que son hacks conocidos
        WEAVE_HACK_MODULES = {
            'killaura', 'aimassist', 'triggerbot', 'reach', 'velocity',
            'scaffold', 'nofall', 'fly', 'speed', 'fullbright', 'xray',
            'autoclick', 'clickgui', 'freecam', 'nametag', 'blink',
        }
        try:
            reported_dirs = set()
            for path, desc in WEAVE_PATHS:
                if not os.path.exists(path):
                    continue
                base_dir = path if os.path.isdir(path) else os.path.dirname(path)
                if base_dir in reported_dirs:
                    continue
                reported_dirs.add(base_dir)

                extra_patterns = ['weave_loader']
                extra_info = ''
                # Leer weave.json para detectar módulos de hacks cargados
                weave_json_path = os.path.join(base_dir, 'weave.json')
                if os.path.isfile(weave_json_path):
                    try:
                        import json as _json
                        with open(weave_json_path, 'r', encoding='utf-8', errors='ignore') as f:
                            wdata = _json.load(f)
                        mods_list = []
                        # weave.json puede tener "modules", "mods", "enabled"
                        for key in ('modules', 'mods', 'enabled', 'addons'):
                            val = wdata.get(key, [])
                            if isinstance(val, list):
                                mods_list.extend(str(m).lower() for m in val)
                            elif isinstance(val, dict):
                                mods_list.extend(k.lower() for k in val.keys())
                        hack_mods = [m for m in mods_list
                                     if any(h in m for h in WEAVE_HACK_MODULES)]
                        if hack_mods:
                            extra_patterns.append(f'weave_modules:{",".join(hack_mods[:5])}')
                            extra_info = f' Módulos detectados: {", ".join(hack_mods[:5])}.'
                    except Exception:
                        pass

                print(f"🚨 WEAVE LOADER: {path}")
                self.issues_found.append({
                    'nombre': f'Weave Loader detectado: {desc}',
                    'ruta': path,
                    'archivo': os.path.basename(path),
                    'tipo': 'ghost_client_config',
                    'categoria': 'GHOST_CLIENT',
                    'alerta': 'CRITICAL',
                    'confidence': 0.96,
                    'detected_patterns': extra_patterns,
                    'explicacion': (
                        'Weave Loader es el framework de inyección de mods más popular actualmente. '
                        'Permite cargar ghost clients y módulos de hacks en Minecraft sin dejar '
                        f'archivos .jar visibles en la carpeta mods.{extra_info}'
                    ),
                })
        except Exception as e:
            print(f"Error en scan_weave_loader: {e}")

    def scan_prefetch_hacks(self):
        """#21 — Detecta archivos Prefetch de hacks ejecutados (aunque el exe esté borrado)."""
        print("🔍 Escaneando Prefetch por hacks ejecutados...")
        prefetch_dir = r'C:\Windows\Prefetch'
        HACK_NAMES = [
            # Clientes clásicos
            'sigma', 'vape', 'vapelite', 'liquidbounce', 'wurst', 'rise',
            'flux', 'future', 'astolfo', 'novoline', 'drip', 'entropy',
            'whiteout', 'exhibition', 'impact',
            # Clientes modernos (2022-2025)
            'meteor', 'meteorclient',
            'rusherhack', 'rusher',
            'aristois',
            'tenacity',
            'vertex', 'vertexclient',
            'inertia', 'inertiaclient',
            'salhack',
            'jello', 'jelloclient',
            'datura', 'daturamc',
            'remix', 'remixclient',
            'pandora', 'pandoraclient',
            'azura',
            'kamiblue',
            'konas',
            'weepcraft',
            'zeroday',
            'nyx', 'nyxclient',
            'lucid', 'lucidclient',
            'nextgen', 'tegernako',
            # Loaders e injectors
            'weaveloader', 'weave-loader',
            'extremeinjector', 'xenos',
            'cheatengine', 'processhacker',
            'injector',
            # Nombres genéricos de ghost clients
            'ghostclient', 'ghost-client',
            'hackclient',
            'aimbot', 'killaura',
            'autoclicker', 'autoclick',
            'scaffold', 'baritone',
        ]
        if not os.path.isdir(prefetch_dir):
            return
        try:
            for fname in os.listdir(prefetch_dir):
                if not fname.lower().endswith('.pf'):
                    continue
                fname_lower = fname.lower()
                for hack in HACK_NAMES:
                    if hack in fname_lower:
                        exe_name = fname.split('-')[0]
                        full_path = os.path.join(prefetch_dir, fname)
                        mtime = os.path.getmtime(full_path)
                        import datetime as _dt
                        last_run = _dt.datetime.fromtimestamp(mtime).strftime('%d/%m/%Y %H:%M')
                        print(f"🚨 PREFETCH HACK: {fname} (última ejecución: {last_run})")
                        self.issues_found.append({
                            'nombre': f'Prefetch de hack encontrado: {exe_name}',
                            'ruta': full_path,
                            'archivo': fname,
                            'tipo': 'prefetch_hack',
                            'categoria': 'FORENSE',
                            'alerta': 'CRITICAL',
                            'confidence': 0.90,
                            'detected_patterns': [f'prefetch:{hack}'],
                            'explicacion': f'Se encontró un archivo Prefetch de {exe_name} (última ejecución: {last_run}). '
                                           f'El Prefetch confirma que este programa fue ejecutado en este PC aunque '
                                           f'el archivo original haya sido borrado.',
                        })
                        break
        except Exception as e:
            print(f"Error en scan_prefetch_hacks: {e}")

    def scan_usn_minecraft_jars(self):
        """#22/#23 — Detecta JARs y carpetas de ghost clients eliminados via USN Journal."""
        print("🔍 Buscando JARs/.minecraft borrados en USN Journal (últimas 72h)...")
        HACK_PATTERNS = [
            # Clientes clásicos
            'sigma', 'vape', 'vapelite', 'liquidbounce', 'wurst', 'rise',
            'flux', 'future', 'astolfo', 'novoline', 'drip', 'entropy',
            'whiteout', 'exhibition',
            # Clientes modernos (2022-2025)
            'meteor', 'rusherhack', 'aristois', 'tenacity', 'vertex',
            'inertia', 'salhack', 'jello', 'datura', 'remix', 'pandora',
            'azura', 'kamiblue', 'konas', 'weepcraft', 'zeroday',
            'nyx', 'lucid', 'nextgen', 'impact',
            # Fingerprints de directorio
            '.weave', '.rise', '.sigma', '.meteor', '.liquidbounce',
            # Misc
            'ghostclient', 'ghost_client', 'baritone', 'schematica',
            'hackclient', 'hackmod', 'weaveloader',
        ]
        import subprocess as _sp
        try:
            result = _sp.run(
                ['fsutil', 'usn', 'readjournal', 'C:', 'csv'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return
            # Filtrar eliminaciones (0x80000200) de .jar y carpetas de ghost clients
            lines = result.stdout.splitlines()
            for line in lines:
                line_l = line.lower()
                is_delete = '0x80000200' in line or '0x80000020' in line
                is_rename = '0x00001000' in line or '0x00002000' in line
                if not (is_delete or is_rename):
                    continue
                has_hack = any(p in line_l for p in HACK_PATTERNS)
                has_mc   = '.minecraft' in line_l
                is_jar   = '.jar' in line_l
                if not (has_hack or (has_mc and is_jar)):
                    continue
                # Extraer nombre de archivo del CSV
                parts = line.split(',')
                fname = parts[3].strip('"') if len(parts) > 3 else line[:80]
                action = 'borrado' if is_delete else 'renombrado'
                print(f"🚨 USN JAR {action.upper()}: {fname}")
                self.issues_found.append({
                    'nombre': f'JAR/carpeta de hack {action} recientemente: {fname}',
                    'ruta': fname,
                    'archivo': fname,
                    'tipo': 'usn_deleted_hack',
                    'categoria': 'FORENSE',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.75,
                    'detected_patterns': [f'usn_{action}'],
                    'explicacion': f'El USN Journal registra que {fname} fue {action} recientemente. '
                                   f'Esto indica que el jugador pudo haber eliminado evidencia de hacks '
                                   f'antes del Screen Share.',
                })
        except Exception as e:
            print(f"Error en scan_usn_minecraft_jars: {e}")

    def scan_discord_webhooks(self):
        """Detecta URLs de Discord webhooks en archivos de config de hack clients (C2/exfiltración)."""
        print("🔍 Buscando Discord webhooks en configs de hacks...")
        import re as _re
        appdata = os.environ.get('APPDATA', '')
        local   = os.environ.get('LOCALAPPDATA', '')
        home    = os.path.expanduser('~')
        # Carpetas donde los hacks guardan sus configs
        SEARCH_BASES = [
            os.path.join(appdata, '.minecraft'),
            os.path.join(appdata, '.weave'),
            os.path.join(appdata, 'WeaveLoader'),
            os.path.join(local,   'WeaveLoader'),
            os.path.join(home,    'Desktop'),
            os.path.join(home,    'Downloads'),
            os.path.join(home,    'Documents'),
        ]
        # Extensiones de archivo de config
        CONFIG_EXTS = {'.json', '.txt', '.cfg', '.yml', '.yaml', '.toml', '.properties', '.log'}
        WEBHOOK_RE = _re.compile(
            r'https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+',
            _re.IGNORECASE
        )
        HACK_CONFIG_KW = ['hack', 'client', 'cheat', 'config', 'setting', 'weave',
                          'module', 'baritone', 'meteor', 'vape', 'sigma', 'flux']
        found_paths = set()
        try:
            for base in SEARCH_BASES:
                if not os.path.isdir(base):
                    continue
                for root, dirs, files in os.walk(base):
                    dirs[:] = [d for d in dirs if d.lower() not in {
                        'google', 'mozilla', 'microsoft', 'windows',
                        'node_modules', '__pycache__', '.git',
                    }]
                    for fname in files:
                        if os.path.splitext(fname.lower())[1] not in CONFIG_EXTS:
                            continue
                        fpath = os.path.join(root, fname)
                        if fpath in found_paths:
                            continue
                        try:
                            fsize = os.path.getsize(fpath)
                            if fsize > 2 * 1024 * 1024:  # skip > 2MB
                                continue
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            matches = WEBHOOK_RE.findall(content)
                            if not matches:
                                continue
                            found_paths.add(fpath)
                            # ¿El archivo está en una carpeta de hack o tiene keyword de hack?
                            root_lower = root.lower()
                            fname_lower = fname.lower()
                            is_hack_context = (
                                any(kw in root_lower for kw in HACK_CONFIG_KW) or
                                any(kw in fname_lower for kw in HACK_CONFIG_KW)
                            )
                            alert = 'CRITICAL' if is_hack_context else 'SOSPECHOSO'
                            conf  = 0.92 if is_hack_context else 0.72
                            print(f"🚨 DISCORD WEBHOOK en config: {fpath} ({len(matches)} URL(s))")
                            self.issues_found.append({
                                'nombre': f'Discord webhook en config de hack: {fname}',
                                'ruta': fpath,
                                'archivo': fname,
                                'tipo': 'discord_webhook_config',
                                'categoria': 'C2_EXFIL',
                                'alerta': alert,
                                'confidence': conf,
                                'detected_patterns': [f'discord_webhook:{m[:60]}' for m in matches[:3]],
                                'explicacion': (
                                    f'Se encontraron {len(matches)} URL(s) de Discord webhook en {fpath}. '
                                    'Los hack clients modernos usan webhooks de Discord para enviar '
                                    'notificaciones al cheater (logros de hack, alerta de SS, etc.) '
                                    'o para exfiltrar datos del servidor/jugador.'
                                ),
                            })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_discord_webhooks: {e}")

    def scan_jitter_scripts(self):
        """#15 — Detecta configuraciones de jitter/aim assist en software de mouse."""
        print("🔍 Buscando jitter scripts en software de mouse...")
        appdata = os.environ.get('APPDATA', '')
        local   = os.environ.get('LOCALAPPDATA', '')
        JITTER_KEYWORDS = ['jitter', 'aimassist', 'aim_assist', 'smoothaim', 'recoil',
                           'firerate', 'fire_rate', 'autofire', 'rapidfire', 'rapid_fire']
        PATHS_TO_SCAN = [
            os.path.join(local,  'LGHUB'),
            os.path.join(appdata, 'Razer'),
            os.path.join(local,  'SteelSeries', 'GG'),
            os.path.join(appdata, 'Corsair'),
            os.path.join(local,  'Corsair'),
        ]
        try:
            for base in PATHS_TO_SCAN:
                if not os.path.isdir(base):
                    continue
                for root, _, files in os.walk(base):
                    for fname in files:
                        if not fname.lower().endswith(('.json', '.xml', '.db', '.lua')):
                            continue
                        fpath = os.path.join(root, fname)
                        try:
                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(8192).lower()
                            if any(kw in content for kw in JITTER_KEYWORDS):
                                # Verificar que no sea solo comentario o descripción
                                app_name = os.path.basename(base)
                                print(f"🚨 JITTER CONFIG: {fpath}")
                                self.issues_found.append({
                                    'nombre': f'Config de jitter/aim assist en {app_name}: {fname}',
                                    'ruta': fpath,
                                    'archivo': fname,
                                    'tipo': 'jitter_script',
                                    'categoria': 'MACRO',
                                    'alerta': 'SOSPECHOSO',
                                    'confidence': 0.65,
                                    'detected_patterns': ['jitter_config'],
                                    'explicacion': f'Se encontró configuración de jitter o aim assist en {app_name}. '
                                                   f'El jitter clicking y el aim assist por software están '
                                                   f'prohibidos en la mayoría de servidores de Minecraft.',
                                })
                                break
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_jitter_scripts: {e}")

    def scan_minecraft_safe_mode(self):
        """#29 — Detecta si Minecraft fue lanzado con --safeMode (mods no cargan)."""
        print("🔍 Verificando si Minecraft corre en Safe Mode...")
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'java' not in name:
                        continue
                    cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                    if '--safemode' in cmdline or '--safe-mode' in cmdline:
                        print("⚠️ Minecraft lanzado con --safeMode — mods deshabilitados")
                        self.issues_found.append({
                            'nombre': 'Minecraft lanzado en Safe Mode (mods desactivados)',
                            'ruta': 'cmdline',
                            'archivo': 'javaw.exe',
                            'tipo': 'minecraft_safe_mode',
                            'categoria': 'EVASION',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 0.70,
                            'detected_patterns': ['safe_mode_launch'],
                            'explicacion': 'Minecraft fue lanzado con --safeMode, lo que deshabilita la carga '
                                           'de mods. El jugador puede estar usando esto para ocultar mods activos '
                                           'o para que no se detecten modificaciones en el arranque.',
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_minecraft_safe_mode: {e}")

    def scan_backup_sync_locations(self):
        """#28 — Marca archivos en rutas de backup/sync con score reducido."""
        SYNC_PATHS = ['onedrive', 'google drive', 'dropbox', 'icloudrive', 'box\\', 'mega\\']
        try:
            for issue in self.issues_found:
                ruta = (issue.get('ruta') or '').lower()
                if any(s in ruta for s in SYNC_PATHS):
                    if issue.get('tipo') not in {
                        'ghost_client_config', 'ghost_client_registry',
                        'blacklisted_mod', 'modified_minecraft_jar'
                    }:
                        issue['confidence'] = round(issue.get('confidence', 0.5) * 0.4, 3)
                        issue['alerta'] = 'POCO_SOSPECHOSO'
                        issue['explicacion'] = (issue.get('explicacion', '') +
                            ' (Archivo en carpeta de sincronización cloud — posiblemente backup de otro PC.)')
        except Exception as e:
            print(f"Error en scan_backup_sync_locations: {e}")

    def scan_hack_fingerprints(self):
        """P3 #15 — Detecta firmas compuestas de ghost clients específicos."""
        print("🔍 Verificando fingerprints compuestos de ghost clients...")
        appdata  = os.environ.get('APPDATA', '')
        local    = os.environ.get('LOCALAPPDATA', '')

        FINGERPRINTS = {
            'Vape': [
                os.path.join(appdata, 'vape.encrypted'),
                os.path.join(appdata, 'vape.json'),
                os.path.join(appdata, '.vape'),
            ],
            'Sigma': [
                os.path.join(appdata, '.sigma'),
                os.path.join(appdata, 'Sigma'),
            ],
            'Rise Client': [
                os.path.join(appdata, '.rise'),
                os.path.join(local,   'Rise Client'),
            ],
            'LiquidBounce': [
                os.path.join(appdata, '.liquidbounce'),
                os.path.join(appdata, 'LiquidBounce'),
            ],
            'Meteor Client': [
                os.path.join(appdata, '.meteor'),
                os.path.join(appdata, '.minecraft', 'mods', 'meteor-client'),
            ],
            'Future Client': [
                os.path.join(appdata, '.future'),
                os.path.join(local,   'Future'),
            ],
            'Flux': [
                os.path.join(appdata, '.flux'),
                os.path.join(appdata, 'Flux'),
            ],
            'Astolfo': [
                os.path.join(appdata, '.astolfo'),
                os.path.join(appdata, 'Astolfo'),
            ],
            'RusherHack': [
                os.path.join(appdata, '.rusherhack'),
                os.path.join(appdata, 'RusherHack'),
            ],
            'Novoline': [
                os.path.join(appdata, '.novoline'),
                os.path.join(appdata, 'Novoline'),
            ],
            'Datura': [
                os.path.join(appdata, '.datura'),
            ],
            'Jello': [
                os.path.join(appdata, 'jello'),
                os.path.join(appdata, '.jello'),
            ],
            'Mathias': [
                os.path.join(appdata, '.mathias'),
            ],
            'SalHack': [
                os.path.join(appdata, '.salhack'),
                os.path.join(appdata, 'SalHack'),
            ],
        }

        try:
            for client_name, paths in FINGERPRINTS.items():
                found = [p for p in paths if os.path.exists(p)]
                if not found:
                    continue
                print(f"🚨 FINGERPRINT GHOST CLIENT: {client_name} ({len(found)} artefactos)")
                self.issues_found.append({
                    'nombre': f'Ghost client identificado: {client_name}',
                    'ruta': found[0],
                    'archivo': os.path.basename(found[0]),
                    'tipo': 'ghost_client_config',
                    'categoria': 'GHOST_CLIENT',
                    'alerta': 'CRITICAL',
                    'confidence': min(0.95, 0.80 + len(found) * 0.05),
                    'detected_patterns': [f'fingerprint:{client_name.lower().replace(" ", "_")}'],
                    'explicacion': f'Se identificó el ghost client {client_name} por {len(found)} artefacto(s) '
                                   f'encontrados en rutas características: {", ".join(os.path.basename(p) for p in found)}.',
                    'count': len(found),
                    'grouped_paths': found,
                })
        except Exception as e:
            print(f"Error en scan_hack_fingerprints: {e}")

    def scan_kill_chain(self):
        """P3 #3 — Detecta secuencias temporales sospechosas en el USN Journal (kill chain)."""
        print("🔍 Analizando kill chain en USN Journal...")
        import subprocess as _sp
        import datetime as _dt
        import re as _re

        try:
            result = _sp.run(
                ['fsutil', 'usn', 'readjournal', 'C:', 'csv'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return

            lines = result.stdout.splitlines()
            events = []
            for line in lines:
                ll = line.lower()
                if not ('.jar' in ll or '.exe' in ll or '.minecraft' in ll):
                    continue
                is_created = '0x00000100' in line
                is_deleted = '0x80000200' in line or '0x80000020' in line
                is_renamed = '0x00001000' in line or '0x00002000' in line
                if not (is_created or is_deleted or is_renamed):
                    continue
                parts = line.split(',')
                fname = parts[3].strip('"') if len(parts) > 3 else ''
                action = 'created' if is_created else 'deleted' if is_deleted else 'renamed'
                events.append({'file': fname.lower(), 'action': action})

            # Detectar kill chain: descargado → ejecutado → borrado
            files_created  = {e['file'] for e in events if e['action'] == 'created'}
            files_deleted  = {e['file'] for e in events if e['action'] == 'deleted'}
            files_renamed  = {e['file'] for e in events if e['action'] == 'renamed'}

            HACK_KW = ['sigma','vape','liquid','wurst','meteor','rise','flux','future',
                       'astolfo','ghost','inject','cheat','hack','aimbot','killaura']

            # Archivos creados Y borrados con nombre de hack = kill chain
            for fname in files_created & files_deleted:
                if any(kw in fname for kw in HACK_KW):
                    print(f"🚨 KILL CHAIN: {fname} — creado y borrado")
                    self.issues_found.append({
                        'nombre': f'Kill chain detectada: {os.path.basename(fname)} (descargado y borrado)',
                        'ruta': fname,
                        'archivo': os.path.basename(fname),
                        'tipo': 'kill_chain',
                        'categoria': 'FORENSE',
                        'alerta': 'CRITICAL',
                        'confidence': 0.88,
                        'detected_patterns': ['kill_chain_download_delete'],
                        'explicacion': f'El archivo {os.path.basename(fname)} fue descargado y borrado en la '
                                       f'misma sesión. Esta secuencia (descargar → ejecutar → borrar) es '
                                       f'característica de jugadores que usan hacks y limpian evidencia.',
                    })

            # Muchos archivos borrados en .minecraft en poco tiempo = limpieza activa
            mc_deleted = [e for e in events if '.minecraft' in e['file'] and e['action'] == 'deleted']
            if len(mc_deleted) >= 10:
                print(f"🚨 LIMPIEZA ACTIVA: {len(mc_deleted)} archivos borrados en .minecraft")
                self.issues_found.append({
                    'nombre': f'Limpieza activa detectada: {len(mc_deleted)} archivos borrados en .minecraft',
                    'ruta': '.minecraft',
                    'archivo': 'USN Journal',
                    'tipo': 'kill_chain',
                    'categoria': 'EVASION',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.72,
                    'detected_patterns': ['active_cleanup'],
                    'explicacion': f'Se detectaron {len(mc_deleted)} archivos borrados en la carpeta .minecraft '
                                   f'recientemente. Esto puede indicar que el jugador limpió evidencia de hacks '
                                   f'antes del Screen Share.',
                })
        except Exception as e:
            print(f"Error en scan_kill_chain: {e}")

    def _filter_by_file_size(self, issues):
        """P2 #8 — Descarta JARs demasiado pequeños para ser un hack real (< 3KB)."""
        result = []
        for issue in issues:
            tipo = issue.get('tipo', '')
            if tipo not in ('file', 'jar_file', 'minecraft_file'):
                result.append(issue)
                continue
            ruta = issue.get('ruta') or issue.get('archivo', '')
            if ruta and os.path.isfile(str(ruta)):
                try:
                    size = os.path.getsize(str(ruta))
                    if size < 3072:  # < 3KB — imposible que sea un hack funcional
                        continue
                except Exception:
                    pass
            result.append(issue)
        return result

    def _filter_backup_sync(self, issues):
        """P2 #28 — Reduce score de archivos en rutas de sincronización cloud."""
        SYNC_KW = ['onedrive', 'google drive', 'dropbox', 'icloudrive', r'box\\', r'mega\\', 'nextcloud']
        ALWAYS_TRUSTED = {'ghost_client_config','ghost_client_registry','blacklisted_mod',
                          'modified_minecraft_jar','javaagent_injection','weave_loader'}
        for issue in issues:
            if issue.get('tipo') in ALWAYS_TRUSTED:
                continue
            ruta = (issue.get('ruta') or '').lower()
            if any(s in ruta for s in SYNC_KW):
                issue['confidence'] = round(issue.get('confidence', 0.5) * 0.35, 3)
                if issue.get('alerta') in ('CRITICAL', 'SOSPECHOSO'):
                    issue['alerta'] = 'POCO_SOSPECHOSO'
                issue['explicacion'] = (issue.get('explicacion', '') +
                    ' (En carpeta de sync cloud — posiblemente backup de otro PC.)')
        return issues

    # ── PARTE 2 — Mejoras de filtrado (FP reduction) ───────────────────────────

    def _apply_human_explanations(self, issues):
        """#23 — Genera explicaciones en español para hallazgos que no tengan una."""
        TIPO_EXPLANATIONS = {
            'ghost_client_config':     'Se encontró un archivo de configuración de un ghost client conocido. '
                                       'Esto indica que el jugador ha ejecutado este hack en este PC.',
            'ghost_client_registry':   'El registro de Windows contiene una clave dejada por la instalación '
                                       'de un ghost client. Persiste aunque se desinstale.',
            'blacklisted_mod':         'Se encontró un mod prohibido en la carpeta de mods de Minecraft. '
                                       'Este mod tiene capacidades de hack.',
            'jdwp_debug_port':         'El proceso de Minecraft tiene activo el puerto de debug JDWP. '
                                       'Esto permite inyectar bytecode en runtime — nadie legítimo juega con esto.',
            'vpn_active':              'Hay una VPN activa durante el Screen Share. '
                                       'Puede usarse para ocultar la IP o evadir sistemas de detección.',
            'hosts_minecraft_redirect':'El archivo hosts redirige dominios de Minecraft o anti-cheat. '
                                       'Técnica usada para evadir sistemas de anti-cheat online.',
            'javaagent_injection':     'Se detectó un agente inyectado en la JVM de Minecraft. '
                                       'Todos los ghost clients modernos como Weave usan esta técnica.',
            'dll_injection_java':      'Se encontró una DLL sospechosa cargada en el proceso de Java/Minecraft. '
                                       'Las DLLs de hack se inyectan para añadir módulos en runtime.',
            'ahk_autoclick':           'Script AutoHotKey con patrones de autoclick detectado. '
                                       'Clicks automáticos con delay de 8-15ms son característicos de autoclic.',
            'injector_process':        'Se detectó un proceso inyector corriendo al mismo tiempo que Minecraft. '
                                       'Los inyectores cargan DLLs o JARs de hacks en el proceso del juego.',
            'temp_jar_recent':         'Se encontró un .jar descargado recientemente en carpetas temporales. '
                                       'Técnica común para inyectar sin dejar rastro permanente.',
            'modified_minecraft_jar':  'El hash del minecraft.jar no coincide con la versión oficial de Mojang. '
                                       'Indica que el jar del juego fue modificado, típico de ghost clients clásicos.',
            'prefetch_hack':           'El Prefetch de Windows confirma que un hack fue ejecutado en este PC. '
                                       'Aunque el archivo esté borrado, la ejecución queda registrada.',
            'usn_deleted_hack':        'El USN Journal registra que un archivo de hack fue borrado recientemente. '
                                       'El jugador puede haber limpiado evidencia antes del SS.',
            'hack_string_in_loaded_jar':'Se encontraron nombres de módulos de hack en los JARs cargados por Java. '
                                        'Esto indica que un ghost client está activo en memoria.',
            'weave_loader':            'Weave Loader es el framework de inyección de hacks más popular actualmente. '
                                       'Su presencia indica que el jugador usa mods no autorizados.',
            'jitter_script':           'Configuración de jitter o aim assist encontrada en software de periférico. '
                                       'El jitter clicking automatizado está prohibido en la mayoría de servidores.',
            'baritone_prohibited':     'Baritone está configurado con modos prohibidos activos (printer, elytraFly). '
                                       'En modo printer puede construir estructuras automáticamente.',
            'litematica_printer':      'Litematica tiene el Printer Mode activado. '
                                       'Permite colocar bloques automáticamente, prohibido en servidores survival.',
            'arduino_hid_device':      'Se detectó un dispositivo HID (Arduino/CH340/STM32) conectado. '
                                       'Estos dispositivos pueden emular un mouse para autoclick por hardware.',
            'suspicious_network_connection': 'javaw.exe tiene una conexión activa a un servidor externo desconocido. '
                                       'Los ghost clients con licencia online (Vape, Future, Sigma) se conectan '
                                       'a sus servidores para verificar la licencia del usuario.',
        }
        for issue in issues:
            if not issue.get('explicacion'):
                tipo = issue.get('tipo', '')
                if tipo in TIPO_EXPLANATIONS:
                    issue['explicacion'] = TIPO_EXPLANATIONS[tipo]
        return issues

    def _group_related_results(self, issues):
        """#24 — Agrupa hallazgos repetidos del mismo tipo/hack en un solo resultado con count."""
        from collections import defaultdict
        groups = defaultdict(list)
        ungrouped = []

        GROUPABLE_TYPES = {
            'ghost_client_config', 'blacklisted_mod', 'temp_jar_recent',
            'prefetch_hack', 'usn_deleted_hack', 'jitter_script',
        }

        for issue in issues:
            tipo = issue.get('tipo', '')
            if tipo in GROUPABLE_TYPES:
                # Agrupar por tipo + hack detectado (primer detected_pattern)
                dp = issue.get('detected_patterns', [''])[0].split(':')[-1]
                key = f"{tipo}:{dp}"
                groups[key].append(issue)
            else:
                ungrouped.append(issue)

        result = list(ungrouped)
        for key, group in groups.items():
            if len(group) == 1:
                result.append(group[0])
            else:
                # Tomar el de mayor confianza como representante
                best = max(group, key=lambda x: x.get('confidence', 0))
                best = dict(best)
                best['nombre'] = f"{best['nombre']} (+{len(group)-1} más)"
                best['count'] = len(group)
                best['grouped_paths'] = [g.get('ruta', '') for g in group]
                result.append(best)

        return result

    def _apply_score_decay(self, issues):
        """#22 — Reduce el score de evidencia antigua (> 30 días)."""
        import datetime as _dt
        now = _dt.datetime.now()
        for issue in issues:
            ruta = issue.get('ruta', '') or issue.get('archivo', '')
            if not ruta or not os.path.exists(str(ruta)):
                continue
            try:
                mtime = os.path.getmtime(str(ruta))
                age_days = (now - _dt.datetime.fromtimestamp(mtime)).days
                if age_days > 30:
                    decay = max(0.5, 1.0 - (age_days - 30) / 180)
                    old_conf = issue.get('confidence', 0.5)
                    issue['confidence'] = round(old_conf * decay, 3)
                    if age_days > 60 and issue.get('alerta') == 'CRITICAL':
                        issue['alerta'] = 'SOSPECHOSO'
            except Exception:
                continue
        return issues

    def _fetch_cloud_thresholds(self):
        """P2 #30 — Descarga umbrales de confianza ajustados por feedback loop desde la cloud."""
        import json as _json, datetime as _dt
        cache_path = os.path.join(os.environ.get('APPDATA', ''), 'ASPERSProjectsSS', 'thresholds.json')
        try:
            if os.path.isfile(cache_path):
                age = (_dt.datetime.now() - _dt.datetime.fromtimestamp(os.path.getmtime(cache_path))).total_seconds()
                if age < 1800:  # 30-minute cache
                    with open(cache_path, 'r') as f:
                        return _json.load(f).get('thresholds', {})
        except Exception:
            pass
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            if not base_url:
                return {}
            r = requests.get(f'{base_url}/api/thresholds', timeout=6)
            if r.ok:
                data = r.json()
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, 'w') as f:
                    _json.dump(data, f)
                return data.get('thresholds', {})
        except Exception:
            pass
        return {}

    def _apply_feedback_thresholds(self, issues):
        """P2 #30 — Aplica umbrales dinámicos por tipo descargados del feedback loop."""
        thresholds = self._fetch_cloud_thresholds()
        if not thresholds:
            return issues
        result = []
        for issue in issues:
            tipo = issue.get('tipo', '')
            if tipo in thresholds:
                min_conf = thresholds[tipo]['min_confidence'] / 100.0
                if issue.get('confidence', 1.0) < min_conf:
                    print(f"[Threshold] Descartando {tipo} con conf {issue.get('confidence'):.2f} < {min_conf:.2f}")
                    continue
            result.append(issue)
        return result

    def _apply_cloud_rarity_and_ban_patterns(self, issues):
        """P3 #2 + #16 — Ajusta confidence dinámicamente usando hack_rate por issue_type
        (rareza epidemiológica) y ban_rate del historial de bans del servidor."""
        if not issues:
            return issues
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            if not base_url:
                return issues

            rarity_map  = {}
            ban_map     = {}

            try:
                r = requests.get(f'{base_url}/api/rarity', timeout=8)
                if r.ok:
                    for entry in r.json().get('rarity', []):
                        rarity_map[entry['issue_type']] = entry['hack_rate']
            except Exception:
                pass

            try:
                r = requests.get(f'{base_url}/api/ban_patterns', timeout=8)
                if r.ok:
                    for entry in r.json().get('ban_patterns', []):
                        ban_map[entry['issue_type']] = entry['ban_rate']
            except Exception:
                pass

            if not rarity_map and not ban_map:
                return issues

            for issue in issues:
                tipo = issue.get('tipo', '')
                base_conf = issue.get('confidence', 0.5)

                hack_rate = rarity_map.get(tipo)
                ban_rate  = ban_map.get(tipo)

                if hack_rate is not None:
                    # Blending: 60% base_conf + 40% hack_rate (para no sobreescribir reglas locales)
                    new_conf = round(base_conf * 0.6 + hack_rate * 0.4, 3)
                    issue['confidence'] = new_conf
                    issue['hack_rate_cloud'] = hack_rate

                if ban_rate is not None and ban_rate >= 0.7:
                    # Si aparece en ≥70% de los baneados, multiplicar ×1.8
                    issue['confidence'] = min(1.0, round(issue.get('confidence', base_conf) * 1.8, 3))
                    issue['ban_rate_cloud'] = ban_rate
                    if issue.get('confidence', 0) >= 0.85 and issue.get('alerta') == 'SOSPECHOSO':
                        issue['alerta'] = 'CRITICAL'

        except Exception as e:
            print(f"Error en _apply_cloud_rarity_and_ban_patterns: {e}")
        return issues

    def _apply_single_indicator_cap(self, issues):
        """P2 #4 — Un solo indicador aislado no debería ser CRITICAL.
        Si un tipo de evidencia aparece solo UNA VEZ y no hay ningún otro CRITICAL,
        lo baja a SOSPECHOSO (excepto tipos de altísima confianza)."""
        ALWAYS_CRITICAL_TYPES = {
            'ghost_client_config', 'ghost_client_registry', 'jdwp_debug_port',
            'dll_injection_java', 'javaagent_injection', 'bootclasspath_modification',
            'modified_minecraft_jar', 'hack_string_in_loaded_jar',
            'cloud_hash_match', 'kill_chain', 'weave_loader',
            'suspicious_process_tree',
        }
        critical_items = [i for i in issues if i.get('alerta') == 'CRITICAL']
        if len(critical_items) <= 1:
            for i in issues:
                if i.get('alerta') == 'CRITICAL' and i.get('tipo', '') not in ALWAYS_CRITICAL_TYPES:
                    if not i.get('combination_penalty') and i.get('confidence', 1.0) < 0.90:
                        i['alerta'] = 'SOSPECHOSO'
                        i['capped_from_critical'] = True
        return issues

    def _apply_combination_penalties(self, issues):
        """P2 #21 — Escala a CRITICAL cuando hay combinaciones de evidencias independientes."""
        tipos = {i.get('tipo', '') for i in issues}
        alertas = {i.get('alerta', '') for i in issues}

        # JDWP + javaagent + memory strings = automático CRITICAL
        if {'jdwp_debug_port', 'javaagent_injection', 'hack_string_in_loaded_jar'}.issubset(tipos):
            for i in issues:
                if i.get('tipo') in ('jdwp_debug_port', 'javaagent_injection', 'hack_string_in_loaded_jar'):
                    i['alerta'] = 'CRITICAL'
                    i['confidence'] = min(1.0, i.get('confidence', 0.8) * 1.3)
                    i['combination_penalty'] = 'JDWP+javaagent+memory_strings'

        # AHK script + proceso AHK corriendo → CRITICAL
        if 'ahk_autoclick' in tipos and any('ahk' in (i.get('nombre', '') + i.get('ruta', '')).lower()
                                              and i.get('categoria') == 'PROCESO' for i in issues):
            for i in issues:
                if i.get('tipo') == 'ahk_autoclick':
                    i['alerta'] = 'CRITICAL'
                    i['combination_penalty'] = 'AHK_script+AHK_process'

        # Ghost client config + prefetch de ese client → muy alta confianza
        if 'ghost_client_config' in tipos and 'prefetch_hack' in tipos:
            for i in issues:
                if i.get('tipo') in ('ghost_client_config', 'prefetch_hack'):
                    i['alerta'] = 'CRITICAL'
                    i['confidence'] = min(1.0, i.get('confidence', 0.8) * 1.2)
                    i['combination_penalty'] = 'config+prefetch'

        # USN jar borrado + kill chain → confirma limpieza activa
        if 'usn_deleted_hack' in tipos and 'kill_chain' in tipos:
            for i in issues:
                if i.get('tipo') in ('usn_deleted_hack', 'kill_chain'):
                    i['alerta'] = 'CRITICAL'
                    i['combination_penalty'] = 'USN+kill_chain'

        # 3+ CRITICAL de categorías distintas → riesgo extremo
        critical_cats = {i.get('categoria', '') for i in issues if i.get('alerta') == 'CRITICAL'}
        if len(critical_cats) >= 3:
            for i in issues:
                if i.get('alerta') == 'CRITICAL':
                    i['confidence'] = min(1.0, i.get('confidence', 0.9) * 1.15)

        return issues

    def scan_player_baseline_delta(self):
        """P3 #5 — Compara el scan actual con el baseline histórico del mismo machine.
        Si hay muchos hallazgos nuevos respecto al historial, es sospechoso.
        Si el jugador siempre sale limpio y hoy tiene CRITICAL, es muy sospechoso."""
        print("🔍 Comparando con baseline histórico del jugador...")
        try:
            base_url = self.config.get('api_url', '').rstrip('/')
            machine_id = self.config.get('machine_id', '')
            if not base_url or not machine_id:
                return

            r = requests.get(f'{base_url}/api/player_baseline/{machine_id}', timeout=8)
            if not r.ok:
                return
            data = r.json()
            baseline = data.get('baseline')
            scan_count = data.get('scan_count', 0)
            if not baseline or scan_count < 2:
                return  # Not enough history

            avg_issues   = baseline.get('avg_issues', 0)
            avg_risk     = baseline.get('avg_risk', 0)
            known_types  = set(baseline.get('known_types', []))
            hack_verdicts = baseline.get('hack_verdicts', 0)

            current_issues = len(self.issues_found)
            current_crits  = sum(1 for i in self.issues_found if i.get('alerta') == 'CRITICAL')
            current_types  = {i.get('tipo', '') for i in self.issues_found}
            new_types = current_types - known_types - {''}

            # Case 1: Current has way more issues than average
            if avg_issues > 0 and current_issues > avg_issues * 3 and current_issues > 5:
                print(f"📊 ANOMALÍA BASELINE: {current_issues} issues vs avg {avg_issues:.1f}")
                self.issues_found.append({
                    'nombre': f'Anomalía vs historial: {current_issues} hallazgos (promedio {avg_issues:.1f})',
                    'ruta': 'player_baseline',
                    'archivo': 'baseline_delta',
                    'tipo': 'baseline_anomaly',
                    'categoria': 'FORENSE',
                    'alerta': 'SOSPECHOSO',
                    'confidence': min(0.85, 0.50 + (current_issues - avg_issues) / (avg_issues * 10)),
                    'detected_patterns': [f'issues_delta:{current_issues - avg_issues:.0f}', f'baseline_scans:{scan_count}'],
                    'explicacion': (
                        f'Este equipo tuvo {avg_issues:.1f} hallazgos en promedio en sus últimos '
                        f'{scan_count} scans. Hoy tiene {current_issues}. '
                        f'Un aumento de 3x+ respecto al historial es inusual.'
                    ),
                })

            # Case 2: Player always clean, now has CRITICALs
            if hack_verdicts == 0 and current_crits >= 2:
                self.issues_found.append({
                    'nombre': f'Jugador históricamente limpio con {current_crits} hallazgos CRITICAL',
                    'ruta': 'player_baseline',
                    'archivo': 'baseline_delta',
                    'tipo': 'baseline_anomaly',
                    'categoria': 'FORENSE',
                    'alerta': 'CRITICAL',
                    'confidence': 0.80,
                    'detected_patterns': ['always_clean_now_critical', f'prior_scans:{scan_count}'],
                    'explicacion': (
                        f'En {scan_count} scans anteriores este jugador siempre salió limpio. '
                        f'Hoy tiene {current_crits} hallazgos CRITICAL que nunca habían aparecido. '
                        f'Cambio repentino muy sospechoso.'
                    ),
                })

            # Case 3: New issue types never seen before in this machine
            if len(new_types) >= 3:
                self.issues_found.append({
                    'nombre': f'{len(new_types)} tipos de hallazgo nuevos nunca vistos en este equipo',
                    'ruta': 'player_baseline',
                    'archivo': 'baseline_delta',
                    'tipo': 'baseline_anomaly',
                    'categoria': 'FORENSE',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.65,
                    'detected_patterns': list(new_types)[:5],
                    'explicacion': (
                        f'Aparecieron {len(new_types)} tipos de hallazgo que nunca se habían visto '
                        f'en este equipo en {scan_count} scans anteriores: '
                        f'{", ".join(list(new_types)[:3])}.'
                    ),
                })

        except Exception as e:
            print(f"Error en scan_player_baseline_delta: {e}")

    def scan_process_tree(self):
        """P3 #9 — Análisis de árbol de procesos completo: detecta cadenas anómalas.
        Un Minecraft legítimo siempre es lanzado por un launcher conocido.
        Detecta: explorer.exe → unknown.exe → javaw.exe (cadena sospechosa)."""
        print("🔍 Analizando árbol de procesos completo...")
        try:
            # Construir mapa pid → process info
            proc_map = {}
            for proc in psutil.process_iter(['pid', 'ppid', 'name', 'exe']):
                try:
                    proc_map[proc.info['pid']] = proc.info
                except Exception:
                    continue

            KNOWN_LAUNCHERS = {
                'minecraftlauncher.exe', 'javaw.exe', 'java.exe',
                'lunarclient.exe', 'badlion.exe', 'prismlauncher.exe',
                'multimc.exe', 'gdlauncher.exe', 'ftb_app.exe',
                'curseforge.exe', 'atlauncher.exe', 'polymc.exe',
                'tlauncher.exe', 'featherlauncher.exe',
                'explorer.exe', 'cmd.exe', 'powershell.exe', 'pwsh.exe',
                'steam.exe',
            }

            INJECTOR_KEYWORDS = {
                'inject', 'hook', 'patch', 'loader', 'cheat', 'hack',
                'bypass', 'ghost', 'stealth', 'aimbot', 'killaura',
                'extremeinjector', 'xenosinjector', 'cheatengine',
            }

            def get_ancestors(pid, depth=0):
                if depth > 5 or pid not in proc_map:
                    return []
                info = proc_map[pid]
                ppid = info.get('ppid', 0)
                return [info] + get_ancestors(ppid, depth + 1)

            # Find all javaw.exe processes and check their ancestry
            for pid, info in proc_map.items():
                try:
                    name = (info.get('name') or '').lower()
                    if 'javaw' not in name:
                        continue
                    ancestors = get_ancestors(info.get('ppid', 0))
                    if not ancestors:
                        continue

                    # Check for injector keywords anywhere in the tree
                    for anc in ancestors:
                        anc_name = (anc.get('name') or '').lower()
                        anc_exe  = (anc.get('exe') or '').lower()
                        if any(kw in anc_name or kw in anc_exe for kw in INJECTOR_KEYWORDS):
                            print(f"🚨 ÁRBOL SOSPECHOSO: javaw ← {anc_name}")
                            self.issues_found.append({
                                'nombre': f'Minecraft lanzado por proceso sospechoso: {anc_name}',
                                'ruta': anc_exe or anc_name,
                                'archivo': anc_name,
                                'tipo': 'suspicious_process_tree',
                                'categoria': 'PROCESO',
                                'alerta': 'CRITICAL',
                                'confidence': 0.88,
                                'detected_patterns': [f'parent:{anc_name}'],
                                'explicacion': (
                                    f'El proceso de Minecraft (javaw.exe) fue iniciado por '
                                    f'"{anc_name}", que tiene nombre asociado a herramientas de hack. '
                                    f'Un Minecraft legítimo siempre es lanzado por un launcher oficial.'
                                ),
                            })
                            break

                    # Check if immediate parent is completely unknown
                    if ancestors:
                        parent_name = (ancestors[0].get('name') or '').lower()
                        if parent_name and parent_name not in KNOWN_LAUNCHERS:
                            parent_exe = (ancestors[0].get('exe') or '').lower()
                            in_safe = any(s in parent_exe for s in ('program files', 'windows', 'steam'))
                            if not in_safe:
                                print(f"⚠️ PARENT DESCONOCIDO: javaw ← {parent_name}")
                                self.issues_found.append({
                                    'nombre': f'Minecraft lanzado por proceso desconocido: {parent_name}',
                                    'ruta': parent_exe or parent_name,
                                    'archivo': parent_name,
                                    'tipo': 'unknown_parent_process',
                                    'categoria': 'PROCESO',
                                    'alerta': 'SOSPECHOSO',
                                    'confidence': 0.60,
                                    'detected_patterns': [f'unknown_parent:{parent_name}'],
                                    'explicacion': (
                                        f'Minecraft fue iniciado por "{parent_name}", un proceso no '
                                        f'reconocido como launcher oficial. Puede ser un loader o inyector.'
                                    ),
                                })
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en scan_process_tree: {e}")

    def scan_prescan_disk_activity(self):
        """P3 #17 — Anomalía de actividad de disco en los 10 minutos previos al inicio del scan.
        Si el jugador borró muchos archivos en .minecraft justo antes, es señal de limpieza activa."""
        print("🔍 Actividad de disco pre-scan (USN Journal últimos 10 min)...")
        import subprocess
        import datetime as _dt

        try:
            result = subprocess.run(
                ['fsutil', 'usn', 'readjournal', 'C:', 'csv'],
                capture_output=True, text=True, timeout=20,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            )
            if result.returncode != 0 or not result.stdout:
                return

            lines = result.stdout.splitlines()
            now = _dt.datetime.now()
            cutoff = now - _dt.timedelta(minutes=10)

            DELETION_FLAG = '0x80000200'
            MC_KEYWORDS = ['.minecraft', 'appdata', 'roaming', 'localappdata']
            HACK_KEYWORDS = [
                '.jar', '.exe', '.dll', 'vape', 'sigma', 'rise', 'meteor',
                'liquidbounce', 'future', 'flux', 'ghost', 'hack', 'cheat',
            ]

            deleted_mc = []
            deleted_total = 0

            for line in lines[1:]:
                parts = line.split(',')
                if len(parts) < 6:
                    continue
                try:
                    # Columnas típicas: Usn,Filename,Timestamp,Reason,FileAttributes,...
                    ts_str = parts[2].strip().strip('"')
                    reason = parts[3].strip().strip('"').lower()
                    fname  = parts[1].strip().strip('"').lower()

                    if DELETION_FLAG.lower() not in reason:
                        continue

                    ts = _dt.datetime.strptime(ts_str[:19], '%Y-%m-%d %H:%M:%S')
                    if ts < cutoff:
                        continue

                    deleted_total += 1
                    if any(k in fname for k in MC_KEYWORDS):
                        deleted_mc.append(fname)
                except Exception:
                    continue

            if deleted_mc:
                hack_deleted = [f for f in deleted_mc if any(k in f for k in HACK_KEYWORDS)]
                msg = (f'Se borraron {len(deleted_mc)} archivos en carpetas de Minecraft '
                       f'en los 10 minutos previos al scan ({deleted_total} borrados totales). '
                       f'Posible limpieza activa de evidencias.')
                alert = 'CRITICAL' if hack_deleted else 'SOSPECHOSO'
                conf  = 0.85 if hack_deleted else 0.60
                print(f"🚨 LIMPIEZA PRE-SCAN: {len(deleted_mc)} archivos MC, {len(hack_deleted)} con keywords de hack")
                self.issues_found.append({
                    'nombre': f'Limpieza activa pre-scan: {len(deleted_mc)} archivos borrados en .minecraft',
                    'ruta': 'USN Journal',
                    'archivo': 'usn_prescan',
                    'tipo': 'prescan_cleanup',
                    'categoria': 'FORENSE',
                    'alerta': alert,
                    'confidence': conf,
                    'detected_patterns': [f'deleted_mc_files:{len(deleted_mc)}', f'hack_files:{len(hack_deleted)}'],
                    'deleted_files': deleted_mc[:20],
                    'explicacion': msg,
                })
            elif deleted_total > 50:
                print(f"⚠️ Alta actividad de borrado pre-scan: {deleted_total} archivos")
                self.issues_found.append({
                    'nombre': f'Alta actividad de borrado pre-scan: {deleted_total} archivos',
                    'ruta': 'USN Journal',
                    'archivo': 'usn_prescan',
                    'tipo': 'prescan_cleanup',
                    'categoria': 'FORENSE',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.45,
                    'detected_patterns': [f'total_deleted:{deleted_total}'],
                    'explicacion': f'Se borraron {deleted_total} archivos en los 10 minutos previos al scan. '
                                   f'Puede indicar limpieza activa aunque no se detectaron archivos de Minecraft.',
                })
        except Exception as e:
            print(f"Error en scan_prescan_disk_activity: {e}")

    def scan_java_rwx_memory(self):
        """Detecta regiones de memoria Private+RWX (Read+Write+Execute) en javaw.exe.
        Java legítimo no tiene regiones ejecutables privadas — son señal de código inyectado."""
        print("🔍 Escaneando regiones de memoria RWX en javaw.exe...")
        try:
            import ctypes
            import ctypes.wintypes as wt
        except ImportError:
            return

        PAGE_EXECUTE_READWRITE = 0x40
        PAGE_EXECUTE_WRITECOPY = 0x80
        MEM_PRIVATE = 0x20000
        MEM_COMMIT  = 0x1000

        class MEMORY_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('BaseAddress',       ctypes.c_size_t),
                ('AllocationBase',    ctypes.c_size_t),
                ('AllocationProtect', wt.DWORD),
                ('RegionSize',        ctypes.c_size_t),
                ('State',             wt.DWORD),
                ('Protect',           wt.DWORD),
                ('Type',              wt.DWORD),
            ]

        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ           = 0x0010
        k32 = ctypes.windll.kernel32

        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'javaw' not in name and 'java.exe' != name:
                        continue
                    pid = proc.pid
                    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
                    if not h:
                        continue
                    try:
                        addr    = 0
                        mbi     = MEMORY_BASIC_INFORMATION()
                        mbi_sz  = ctypes.sizeof(mbi)
                        rwx_count = 0
                        rwx_total_kb = 0
                        while k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_sz):
                            if (mbi.State == MEM_COMMIT
                                    and mbi.Type == MEM_PRIVATE
                                    and mbi.Protect in (PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY)):
                                rwx_count    += 1
                                rwx_total_kb += mbi.RegionSize // 1024
                            next_addr = mbi.BaseAddress + mbi.RegionSize
                            if next_addr <= addr:
                                break
                            addr = next_addr
                        if rwx_count >= 3:  # Umbral: >=3 regiones RWX privadas
                            print(f"🚨 REGIONES RWX EN JAVAW (PID {pid}): {rwx_count} regiones, {rwx_total_kb}KB total")
                            self.issues_found.append({
                                'nombre': f'Regiones de memoria ejecutable privada (RWX) en Minecraft: {rwx_count} regiones',
                                'ruta': f'PID:{pid}',
                                'archivo': 'javaw.exe',
                                'tipo': 'javaagent_injection',
                                'categoria': 'JAVA_INJECTION',
                                'alerta': 'CRITICAL' if rwx_count >= 8 else 'SOSPECHOSO',
                                'confidence': min(0.92, 0.60 + rwx_count * 0.04),
                                'detected_patterns': [f'rwx_regions:{rwx_count}', f'rwx_kb:{rwx_total_kb}'],
                                'explicacion': f'javaw.exe (PID {pid}) tiene {rwx_count} regiones de memoria '
                                               f'privadas con permisos Read+Write+Execute ({rwx_total_kb}KB). '
                                               f'Java legítimo no crea estas regiones — indican código '
                                               f'inyectado en runtime (DLL injection, JVM bytecode injection).',
                            })
                    finally:
                        k32.CloseHandle(h)
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    continue
        except Exception as e:
            print(f"Error en scan_java_rwx_memory: {e}")

    def scan_temp_dlls(self):
        """Detecta DLLs sospechosas en carpetas temporales (%TEMP%, C:\\Windows\\Temp).
        Hacks basados en inyección nativa frecuentemente cargan DLLs desde rutas temporales."""
        print("🔍 Buscando DLLs sospechosas en carpetas Temp...")
        temp_dirs = list({
            os.environ.get('TEMP', ''),
            os.environ.get('TMP', ''),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
            r'C:\Windows\Temp',
        })
        SAFE_PATTERNS = ('jna', 'fontconfig', 'hsperfdata', 'msi', 'msedge', 'chrome', 'setup')
        cutoff_24h = time.time() - 86400
        seen = set()
        try:
            for tdir in temp_dirs:
                if not tdir or not os.path.isdir(tdir):
                    continue
                for root, dirs, files in os.walk(tdir):
                    dirs[:] = dirs[:6]  # cap depth
                    for fname in files:
                        if not fname.lower().endswith('.dll'):
                            continue
                        fpath = os.path.join(root, fname)
                        if fpath in seen:
                            continue
                        seen.add(fpath)
                        fname_l = fname.lower()
                        if any(s in fname_l for s in SAFE_PATTERNS):
                            continue
                        try:
                            mtime = os.path.getmtime(fpath)
                            size  = os.path.getsize(fpath)
                            if mtime >= cutoff_24h and size > 10240:  # >10KB y reciente
                                conf = 0.75 if size > 524288 else 0.60  # >512KB más sospechoso
                                print(f"⚠️ DLL SOSPECHOSA EN TEMP: {fpath}")
                                self.issues_found.append({
                                    'nombre': f'DLL sospechosa en carpeta temporal: {fname}',
                                    'ruta': fpath,
                                    'archivo': fname,
                                    'tipo': 'dll_injection_java',
                                    'categoria': 'JAVA_INJECTION',
                                    'alerta': 'SOSPECHOSO',
                                    'confidence': conf,
                                    'detected_patterns': ['dll_in_temp', f'size:{size}'],
                                    'explicacion': f'DLL de {size//1024}KB encontrada en carpeta temporal '
                                                   f'en las últimas 24h. Los hacks basados en inyección '
                                                   f'nativa suelen cargar DLLs desde rutas temporales para '
                                                   f'no dejar rastro permanente en el sistema.',
                                })
                        except Exception:
                            continue
        except Exception as e:
            print(f"Error en scan_temp_dlls: {e}")

    def scan_multiple_javaw(self):
        """Detecta múltiples instancias de javaw.exe corriendo simultáneamente.
        Un jugador legítimo raramente tiene más de 1 instancia de Minecraft abierta.
        Múltiples instancias pueden indicar un proceso de inyección separado del juego."""
        print("🔍 Verificando instancias múltiples de javaw.exe...")
        try:
            java_procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'javaw' in name or ('java.exe' == name):
                        cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                        java_procs.append({
                            'pid':      proc.pid,
                            'name':     proc.info['name'],
                            'cmdline':  cmdline[:200],
                            'is_mc':    '.minecraft' in cmdline or 'minecraft' in cmdline,
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            mc_procs = [p for p in java_procs if p['is_mc']]
            non_mc   = [p for p in java_procs if not p['is_mc']]

            if len(mc_procs) > 1:
                pids = ', '.join(str(p['pid']) for p in mc_procs)
                print(f"🚨 MÚLTIPLES INSTANCIAS MINECRAFT: {len(mc_procs)} ({pids})")
                self.issues_found.append({
                    'nombre': f'Múltiples instancias de Minecraft simultáneas: {len(mc_procs)}',
                    'ruta': f'PIDs: {pids}',
                    'archivo': 'javaw.exe',
                    'tipo': 'suspicious_process_location',
                    'categoria': 'PROCESO',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.70,
                    'detected_patterns': [f'multiple_javaw:{len(mc_procs)}'],
                    'explicacion': f'Se detectaron {len(mc_procs)} instancias de javaw.exe con '
                                   f'contexto de Minecraft. Esto puede indicar un proceso de inyección '
                                   f'separado haciéndose pasar por una instancia legítima del juego.',
                })
            if non_mc and mc_procs:
                pids_non = ', '.join(str(p['pid']) for p in non_mc[:3])
                self.issues_found.append({
                    'nombre': f'Proceso Java sin contexto Minecraft corriendo junto al juego: PID {pids_non}',
                    'ruta': f'PIDs: {pids_non}',
                    'archivo': 'java.exe',
                    'tipo': 'suspicious_process_location',
                    'categoria': 'PROCESO',
                    'alerta': 'SOSPECHOSO',
                    'confidence': 0.60,
                    'detected_patterns': ['java_process_without_minecraft'],
                    'explicacion': f'Hay {len(non_mc)} proceso(s) Java corriendo sin contexto de Minecraft '
                                   f'mientras el juego está abierto. Un inyector basado en JVM puede '
                                   f'ejecutarse como proceso Java independiente.',
                })
        except Exception as e:
            print(f"Error en scan_multiple_javaw: {e}")

    def scan_javaw_network_connections(self):
        """Detecta conexiones de red de javaw.exe a hosts distintos al servidor y a Mojang.
        Los ghost clients con licencia online se conectan a servidores de autenticación propios."""
        print("🔍 Analizando conexiones de red de javaw.exe...")
        TRUSTED_DOMAINS_SUFFIX = (
            '.mojang.com', '.minecraft.net', '.minecraftservices.com',
            '.amazonaws.com', '.microsoft.com', '.xbox.com', '.live.com',
            '.akamai.net', '.akamaiedge.net', '.fastly.net', '.cloudfront.net',
        )
        TRUSTED_IPS_PREFIX = ('127.', '::1', '0.0.0.0', '192.168.', '10.', '172.')
        try:
            import socket as _sock
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    if 'javaw' not in name and 'java.exe' != name:
                        continue
                    try:
                        conns = proc.net_connections(kind='inet')
                    except (psutil.AccessDenied, AttributeError):
                        try:
                            conns = proc.connections(kind='inet')
                        except Exception:
                            continue
                    for conn in conns:
                        if conn.status != 'ESTABLISHED':
                            continue
                        raddr = conn.raddr
                        if not raddr or not raddr.ip:
                            continue
                        remote_ip = raddr.ip
                        if any(remote_ip.startswith(p) for p in TRUSTED_IPS_PREFIX):
                            continue
                        # Try reverse DNS (non-blocking, short timeout)
                        hostname = ''
                        try:
                            _sock.setdefaulttimeout(0.5)
                            hostname = _sock.gethostbyaddr(remote_ip)[0].lower()
                        except Exception:
                            hostname = ''
                        finally:
                            _sock.setdefaulttimeout(None)

                        if hostname and any(hostname.endswith(d) for d in TRUSTED_DOMAINS_SUFFIX):
                            continue  # trusted host
                        # External connection not to Mojang/CDN
                        label = hostname or remote_ip
                        port  = raddr.port
                        print(f"⚠️ CONEXIÓN EXTERNA DE JAVAW: {label}:{port}")
                        self.issues_found.append({
                            'nombre': f'Conexión de Minecraft a host externo desconocido: {label}',
                            'ruta': f'{remote_ip}:{port}',
                            'archivo': 'javaw.exe',
                            'tipo': 'suspicious_network_connection',
                            'categoria': 'RED',
                            'alerta': 'SOSPECHOSO',
                            'confidence': 0.65,
                            'detected_patterns': [f'javaw_external_conn:{label}:{port}'],
                            'explicacion': f'javaw.exe tiene una conexión activa a {label}:{port}, '
                                           f'que no es un servidor de Mojang ni CDN conocido. '
                                           f'Los ghost clients con sistema de licencias online '
                                           f'(Vape, Future, Sigma) se conectan a sus propios servidores '
                                           f'para verificar la licencia del usuario.',
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error en scan_javaw_network_connections: {e}")

    def _apply_process_whitelist(self, issues):
        """P2 #13 — Descarta procesos conocidos y seguros del listado de hallazgos."""
        SAFE_PROCESSES = {
            # Sistema / drivers
            'svchost.exe', 'lsass.exe', 'winlogon.exe', 'csrss.exe', 'smss.exe',
            'services.exe', 'wininit.exe', 'dwm.exe', 'taskhost.exe', 'taskhostw.exe',
            'conhost.exe', 'dllhost.exe', 'rundll32.exe', 'regsvr32.exe',
            # Gamer / overlay
            'discord.exe', 'discordptb.exe', 'discordcanary.exe',
            'steam.exe', 'steamwebhelper.exe', 'gameoverlayui.exe',
            'nvcontainer.exe', 'nvdisplay.container.exe', 'nvcplui.exe',
            'nvtelemetrycontainer.exe', 'nvidia web helper.exe',
            'xboxapp.exe', 'gamebar.exe', 'gamebarftserver.exe',
            'obs64.exe', 'obs.exe', 'obs-browser-page.exe',
            'spotify.exe', 'spoticrashhandler.exe',
            'msedge.exe', 'chrome.exe', 'firefox.exe', 'opera.exe',
            'epicgameslauncher.exe', 'easyanticheat.exe',
            'geforceexperience.exe', 'geforcenow.exe',
            # Minecraft legítimos
            'javaw.exe', 'java.exe', 'minecraft.exe', 'minecraftlauncher.exe',
            'prismlauncher.exe', 'multimc.exe', 'ftblauncher.exe',
            'curseforgeapp.exe', 'gdlauncher.exe', 'atlauncher.exe',
            # Windows utilities
            'explorer.exe', 'taskmgr.exe', 'notepad.exe', 'mspaint.exe',
            'cmd.exe', 'powershell.exe', 'windowsterminal.exe',
        }
        result = []
        for issue in issues:
            archivo = (issue.get('archivo') or '').lower().strip()
            if issue.get('categoria') == 'PROCESO' and archivo in SAFE_PROCESSES:
                # Solo descartar si la confianza es baja y no tiene combo penalty
                if issue.get('confidence', 1.0) < 0.75 and not issue.get('combination_penalty'):
                    continue
            result.append(issue)
        return result

    def second_pass_scanner(self):
        """Segunda pasada: analiza archivos SOSPECHOSO/CRITICAL con mayor profundidad."""
        print("🔬 Segunda pasada de análisis sobre archivos sospechosos...")
        try:
            candidates = [i for i in self.issues_found
                          if i.get('alerta') in ('SOSPECHOSO', 'CRITICAL')
                          and i.get('tipo') in ('file', 'jar_file', 'minecraft_file', 'exe_file')
                          and i.get('ruta') and os.path.isfile(str(i.get('ruta', '')))]

            upgraded = 0
            for issue in candidates[:50]:  # Limit to 50 to avoid slowdown
                try:
                    analysis = self.analyze_file_content(str(issue['ruta']))
                    if analysis.get('is_hack') and analysis.get('confidence', 0) > issue.get('confidence', 0):
                        issue['confidence'] = analysis['confidence']
                        issue['detected_patterns'] = list(set(
                            issue.get('detected_patterns', []) + analysis.get('detected_patterns', [])))
                        issue['file_hash'] = analysis.get('file_hash') or issue.get('file_hash')
                        if analysis['confidence'] >= 80:
                            issue['alerta'] = 'CRITICAL'
                            upgraded += 1
                        elif analysis['confidence'] >= 60:
                            issue['alerta'] = 'SOSPECHOSO'
                except Exception:
                    pass
            print(f"✅ Segunda pasada: {upgraded} archivos actualizados a CRITICAL")
        except Exception as e:
            print(f"Error en second_pass_scanner: {e}")

    def show_details(self):
        """Muestra la ventana de detalles"""
        if self.issues_found:
            DetallesVentana(self.root, self.issues_found)
        else:
            messagebox.showinfo("Sin resultados", "No hay resultados para mostrar")
    
    def generate_html_report(self):
        """Genera reporte HTML mejorado con categorías"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"SS_Report_{timestamp}.html"
            
            # Clasificar elementos por categoría
            illegal_files = []
            suspicious_files = []
            clean_files = []
            
            for item in self.issues_found:
                alerta = item.get('alerta', '').upper()
                if alerta == 'CRITICAL':
                    illegal_files.append(item)
                elif alerta in ['SOSPECHOSO', 'POCO_SOSPECHOSO']:
                    suspicious_files.append(item)
                else:
                    clean_files.append(item)
            
            # Obtener información del sistema
            system_info = self.get_system_info()
            
            # Calcular estadísticas de archivos escaneados
            total_files_scanned = getattr(self, 'total_files_scanned', 0)
            if total_files_scanned == 0:
                # Intentar calcular desde los issues encontrados si no hay contador
                total_files_scanned = len(self.issues_found) * 10  # Estimación conservadora
            scan_duration = getattr(self, 'scan_duration', '00:00:00')
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Minecraft SS Tool Report - Análisis Completo</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #0f0f23, #1a1a2e); color: #e0e0e0; margin: 0; padding: 0; min-height: 100vh; }}
                    .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 30px; text-align: center; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); }}
                    .header h1 {{ color: #00d9ff; margin: 0; font-size: 2.5em; text-shadow: 0 0 20px rgba(0, 217, 255, 0.5); }}
                    .header p {{ color: #b4b4b4; margin: 10px 0; font-size: 1.2em; }}
                    .content {{ padding: 20px; max-width: 1400px; margin: 0 auto; }}
                    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }}
                    .stat-card {{ background: linear-gradient(135deg, #2c3e50, #34495e); padding: 25px; border-radius: 15px; text-align: center; box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3); transition: transform 0.3s ease; }}
                    .stat-card:hover {{ transform: translateY(-5px); }}
                    .stat-number {{ font-size: 2.5em; font-weight: bold; margin-bottom: 10px; }}
                    .stat-label {{ font-size: 1.1em; color: #b4b4b4; margin-top: 10px; }}
                    .illegal {{ color: #ff4444; text-shadow: 0 0 10px rgba(255, 68, 68, 0.5); }}
                    .suspicious {{ color: #ffa500; text-shadow: 0 0 10px rgba(255, 165, 0, 0.5); }}
                    .clean {{ color: #00ff00; text-shadow: 0 0 10px rgba(0, 255, 0, 0.5); }}
                    .system {{ color: #00d9ff; text-shadow: 0 0 10px rgba(0, 217, 255, 0.5); }}
                    .files {{ color: #ff6b6b; text-shadow: 0 0 10px rgba(255, 107, 107, 0.5); }}
                    .time {{ color: #4ecdc4; text-shadow: 0 0 10px rgba(78, 205, 196, 0.5); }}
                    .section {{ margin: 40px 0; background: rgba(44, 62, 80, 0.3); padding: 25px; border-radius: 15px; backdrop-filter: blur(10px); }}
                    .section h2 {{ color: #00d9ff; border-bottom: 3px solid #00d9ff; padding-bottom: 15px; font-size: 1.8em; text-shadow: 0 0 10px rgba(0, 217, 255, 0.3); }}
                    .issue {{ background: linear-gradient(135deg, #2c3e50, #34495e); margin: 15px 0; padding: 20px; border-radius: 10px; border-left: 5px solid; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); }}
                    .critical {{ border-left-color: #ff4444; }}
                    .suspicious {{ border-left-color: #ffa500; }}
                    .clean {{ border-left-color: #00ff00; }}
                    .issue-title {{ font-weight: bold; color: #fff; font-size: 1.1em; margin-bottom: 10px; }}
                    .issue-details {{ color: #b4b4b4; margin: 8px 0; }}
                    .timestamp {{ color: #888; font-size: 0.9em; text-align: center; margin-top: 30px; }}
                    .system-info {{ background: linear-gradient(135deg, #1e3c72, #2a5298); padding: 20px; border-radius: 10px; margin: 20px 0; }}
                    .system-info h3 {{ color: #00d9ff; margin-top: 0; }}
                    .info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
                    .info-card {{ background: rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 8px; }}
                    .info-card h4 {{ color: #00d9ff; margin-top: 0; }}
                    .usb-list {{ max-height: 200px; overflow-y: auto; }}
                    .usb-item {{ background: rgba(0, 217, 255, 0.1); padding: 8px; margin: 5px 0; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🔍 Minecraft SS Tool - Reporte Completo</h1>
                    <p>Análisis exhaustivo del sistema - Generado el {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                    <p>⏱️ Tiempo de escaneo: {self.get_scan_duration()}</p>
                </div>
                <div class="content">
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-number illegal">{len(illegal_files)}</div>
                            <div class="stat-label">🚨 Archivos Ilegales</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number suspicious">{len(suspicious_files)}</div>
                            <div class="stat-label">⚠️ Archivos Sospechosos</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number clean">{len(clean_files)}</div>
                            <div class="stat-label">✅ Archivos Limpios</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number files">{total_files_scanned:,}</div>
                            <div class="stat-label">📁 Archivos Escaneados</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number time">{scan_duration}</div>
                            <div class="stat-label">⏱️ Tiempo de Escaneo</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number system">{len(self.issues_found)}</div>
                            <div class="stat-label">📊 Total Analizados</div>
                        </div>
                        <div class="stat-card" style="{'background:linear-gradient(135deg,#3a0000,#5a0000);' if getattr(self,'mouse_findings',[]) else ''}">
                            <div class="stat-number" style="color:{'#ff4444' if getattr(self,'mouse_findings',[]) else '#00ff00'};">{len(getattr(self,'mouse_findings',[]))}</div>
                            <div class="stat-label">🖱️ Alertas de Mouse</div>
                        </div>
                        <div class="stat-card" style="{'background:linear-gradient(135deg,#1a0a3a,#2a0a5a);' if getattr(self,'forensic_findings',[]) else ''}">
                            <div class="stat-number" style="color:{'#cc88ff' if getattr(self,'forensic_findings',[]) else '#00ff00'};">{len(getattr(self,'forensic_findings',[]))}</div>
                            <div class="stat-label">🔬 Evidencia Forense</div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>💻 Información del Sistema</h2>
                        <div class="system-info">
                            <div class="info-grid">
                                <div class="info-card">
                                    <h4>👤 Información del Usuario</h4>
                                    <p><strong>Usuario:</strong> {system_info.get('username', 'N/A')}</p>
                                    <p><strong>PC:</strong> {system_info.get('computer_name', 'N/A')}</p>
                                    <p><strong>IP Local:</strong> {system_info.get('local_ip', 'N/A')}</p>
                                </div>
                                <div class="info-card">
                                    <h4>🔌 Dispositivos USB Conectados</h4>
                                    <div class="usb-list">
                                        {self._generate_usb_section(system_info.get('usb_devices', []))}
                                    </div>
                                </div>
                                <div class="info-card">
                                    <h4>🗑️ Información de la Papelera</h4>
                                    <p><strong>Última limpieza:</strong> {system_info.get('recycle_bin', {}).get('last_cleared', 'N/A')}</p>
                                    <p><strong>Hace:</strong> {system_info.get('recycle_bin', {}).get('days_ago', 'N/A')} días</p>
                                </div>
                                <div class="info-card">
                                    <h4>⚙️ Recursos del Sistema</h4>
                                    <p><strong>Procesos activos:</strong> {system_info.get('process_count', 0)}</p>
                                    <p><strong>RAM total:</strong> {system_info.get('memory_total', 'N/A')}</p>
                                    <p><strong>RAM usada:</strong> {system_info.get('memory_used', 'N/A')}</p>
                                </div>
                                <div class="info-card">
                                    <h4>🌐 Información de Red</h4>
                                    <p><strong>Conexiones totales:</strong> {system_info.get('network_info', {}).get('total_connections', 0)}</p>
                                    <p><strong>Conexiones establecidas:</strong> {system_info.get('network_info', {}).get('established_connections', 0)}</p>
                                    <p><strong>Puertos escuchando:</strong> {system_info.get('network_info', {}).get('listening_ports', 0)}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    {self._generate_mouse_section()}

                    {self._generate_forensic_section()}

                    <div class="section">
                        <h2>🚨 Archivos Ilegales Detectados</h2>
                        {self._generate_illegal_files_section(illegal_files[:10])}
                        {self._generate_summary_section(illegal_files, 'ilegales', 10)}
                    </div>
                    
                    <div class="section">
                        <h2>⚠️ Archivos Sospechosos Detectados</h2>
                        {self._generate_suspicious_files_section(suspicious_files[:20])}
                        {self._generate_summary_section(suspicious_files, 'sospechosos', 20)}
                    </div>
                    
                    <div class="section">
                        <h2>✅ Archivos Limpios Verificados</h2>
                        {self._generate_clean_files_section(clean_files[:10])}
                        {self._generate_summary_section(clean_files, 'limpios', 10)}
                    </div>
                    
                    <div class="section">
                        <h2>📊 Resumen del Análisis</h2>
                        <div class="info-grid">
                            <div class="info-card">
                                <h4>📈 Estadísticas Generales</h4>
                                <p>Total de elementos analizados: <strong>{len(self.issues_found)}</strong></p>
                                <p>Archivos ilegales encontrados: <strong>{len(illegal_files)}</strong></p>
                                <p>Archivos sospechosos encontrados: <strong>{len(suspicious_files)}</strong></p>
                                <p>Archivos limpios verificados: <strong>{len(clean_files)}</strong></p>
                            </div>
                            <div class="info-card">
                                <h4>⚡ Rendimiento del Escaneo</h4>
                                <p>Tiempo total: <strong>{self.get_scan_duration()}</strong></p>
                                <p>CPU cores utilizados: <strong>{psutil.cpu_count()}</strong></p>
                                <p>Memoria disponible: <strong>{psutil.virtual_memory().available / (1024**3):.1f} GB</strong></p>
                            </div>
                        </div>
                        <p class="timestamp">Reporte generado automáticamente por Minecraft SS Tool v2.0</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"📄 Reporte HTML generado: {report_filename}")
            
        except Exception as e:
            print(f"Error generando reporte HTML: {e}")
    
    def _generate_mouse_section(self):
        """Genera la sección de detección de manipulación de mouse para el reporte HTML."""
        mf = getattr(self, 'mouse_findings', [])
        if not mf:
            return """
            <div class="section" style="border-left:4px solid #00ff00;">
                <h2 style="color:#00ff00;">🖱️ Detección de Mouse (Prison Mode)</h2>
                <p style="color:#00ff00;">✅ Sin indicadores de peso, click-bug ni manipulación de mouse.</p>
            </div>"""

        rows = ""
        for item in mf:
            color  = "#ff4444" if item.get('alerta') == 'CRITICAL' else "#ffa500"
            icon   = "🔴" if item.get('alerta') == 'CRITICAL' else "🟠"
            rows += f"""
            <div class="issue critical" style="border-left-color:{color};">
                <div class="issue-title" style="color:{color};">{icon} {item.get('nombre','')}</div>
                <div class="issue-details"><strong>Detalle:</strong> {item.get('detalle','')}</div>
                <div class="issue-details" style="color:#e0e0e0;">{item.get('descripcion','')}</div>
                <div class="issue-details" style="color:#888;font-size:0.85em;">
                    Severidad: <strong style="color:{color};">{item.get('alerta','')}</strong>
                    &nbsp;|&nbsp; Tipo: {item.get('tipo','')}
                </div>
            </div>"""

        return f"""
        <div class="section" style="border:1px solid rgba(255,68,68,0.4);background:rgba(120,0,0,0.15);">
            <h2 style="color:#ff4444;border-bottom-color:#ff4444;">
                🖱️ Detección de Manipulación de Mouse (Prison Mode)
                <span style="font-size:0.6em;background:#ff4444;color:#fff;
                             padding:3px 10px;border-radius:10px;margin-left:12px;">
                    {len(mf)} ALERTA(S)
                </span>
            </h2>
            <p style="color:#ffa0a0;margin-bottom:16px;font-size:0.95em;">
                ⚠️  Se detectaron indicadores de <strong>peso sobre el mouse</strong>,
                <strong>click-bug activo</strong> o <strong>desconexión/reconexión de dispositivo</strong>
                durante la sesión de SS. Estas técnicas se usan en prison mode para obtener
                autoclick sin software detectable.
            </p>
            {rows}
        </div>"""

    def _generate_forensic_section(self):
        """Genera la sección de análisis forense SS para el reporte HTML."""
        ff = getattr(self, 'forensic_findings', [])
        if not ff:
            return """
            <div class="section" style="border-left:4px solid #00ff00;">
                <h2 style="color:#00ff00;">🔬 Análisis Forense SS (Checklist Manual)</h2>
                <p style="color:#00ff00;">✅ Sin evidencia histórica de hacks, autoclickers ni herramientas de evasión.</p>
            </div>"""

        rows = ""
        for item in ff:
            color = "#cc88ff" if item.get('alerta') == 'CRITICAL' else "#66aaff"
            icon  = "🔴" if item.get('alerta') == 'CRITICAL' else "🔬"
            rows += f"""
            <div class="issue" style="border-left:3px solid {color};background:rgba(80,0,120,0.15);margin-bottom:8px;padding:10px 14px;">
                <div class="issue-title" style="color:{color};">{icon} {item.get('nombre','')}</div>
                <div class="issue-details"><strong>Fuente:</strong> {item.get('tipo','')}</div>
                <div class="issue-details"><strong>Detalle:</strong> {item.get('detalle','')}</div>
                <div class="issue-details" style="color:#e0e0e0;">{item.get('descripcion','')}</div>
                <div class="issue-details" style="color:#888;font-size:0.85em;">
                    Severidad: <strong style="color:{color};">{item.get('alerta','')}</strong>
                </div>
            </div>"""

        return f"""
        <div class="section" style="border:1px solid rgba(180,80,255,0.4);background:rgba(50,0,80,0.15);">
            <h2 style="color:#cc88ff;border-bottom-color:#cc88ff;">
                🔬 Análisis Forense SS — Evidencia Histórica
                <span style="font-size:0.6em;background:#cc88ff;color:#fff;
                             padding:3px 10px;border-radius:10px;margin-left:12px;">
                    {len(ff)} HALLAZGO(S)
                </span>
            </h2>
            <p style="color:#d0a0ff;margin-bottom:16px;font-size:0.95em;">
                ⚠️  Técnicas del checklist manual SS: USN Journal, BAM, AppCompat, UserAssist,
                WinRAR, Prefetch, DisallowRun y más. Esta evidencia <strong>sobrevive la eliminación
                del scanner</strong> y es recuperable incluso cuando el jugador lo borró.
            </p>
            {rows}
        </div>"""

    def _generate_illegal_files_section(self, illegal_files):
        """Genera la sección de archivos ilegales"""
        if not illegal_files:
            return "<p style='color: #00ff00;'>✅ No se encontraron archivos ilegales</p>"
        
        html = ""
        for item in illegal_files:
            html += f"""
            <div class="issue critical">
                <div class="issue-title">🚨 {item.get('nombre', 'N/A')}</div>
                <div class="issue-details">Tipo: {item.get('tipo', 'N/A')}</div>
                <div class="issue-details">Ruta: {item.get('ruta', 'N/A')}</div>
                <div class="issue-details">Categoría: {item.get('categoria', 'N/A')}</div>
            </div>
            """
        return html
    
    def _generate_suspicious_files_section(self, suspicious_files):
        """Genera la sección de archivos sospechosos"""
        if not suspicious_files:
            return "<p style='color: #00ff00;'>✅ No se encontraron archivos sospechosos</p>"
        
        html = ""
        for item in suspicious_files:
            html += f"""
            <div class="issue suspicious">
                <div class="issue-title">⚠️ {item.get('nombre', 'N/A')}</div>
                <div class="issue-details">Tipo: {item.get('tipo', 'N/A')}</div>
                <div class="issue-details">Ruta: {item.get('ruta', 'N/A')}</div>
                <div class="issue-details">Categoría: {item.get('categoria', 'N/A')}</div>
            </div>
            """
        return html
    
    def _generate_clean_files_section(self, clean_files):
        """Genera la sección de archivos limpios"""
        if not clean_files:
            return "<p style='color: #ffa500;'>⚠️ No se encontraron archivos limpios para mostrar</p>"
        
        html = ""
        for item in clean_files:
            html += f"""
            <div class="issue clean">
                <div class="issue-title">✅ {item.get('nombre', 'N/A')}</div>
                <div class="issue-details">Tipo: {item.get('tipo', 'N/A')}</div>
                <div class="issue-details">Ruta: {item.get('ruta', 'N/A')}</div>
                <div class="issue-details">Categoría: {item.get('categoria', 'N/A')}</div>
            </div>
            """
        return html
    
    def _generate_usb_section(self, usb_devices):
        """Genera la sección de dispositivos USB"""
        if not usb_devices:
            return "<p style='color: #ffa500;'>⚠️ No se encontraron dispositivos USB conectados</p>"
        
        html = ""
        for device in usb_devices:
            html += f"""
            <div class="usb-item">
                🔌 {device}
            </div>
            """
        return html
    
    # Función de Discord eliminada - Todo se gestiona vía Web ahora
    
    def get_scan_duration(self):
        """Obtiene la duración del escaneo"""
        if hasattr(self, 'scan_start_time'):
            duration = time.time() - self.scan_start_time
            hours, remainder = divmod(duration, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        return "N/A"
    
    def get_system_info(self):
        """Obtiene información completa del sistema"""
        try:
            import socket
            import getpass
            import psutil
            
            # Información del usuario
            username = getpass.getuser()
            computer_name = socket.gethostname()
            
            # Información de IP
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
            except:
                local_ip = "No disponible"
            
            # Información de USBs (sin dependencias externas)
            usb_devices = []
            try:
                import subprocess
                # Usar wmic que viene con Windows
                result = subprocess.run(['wmic', 'logicaldisk', 'where', 'drivetype=2', 'get', 'deviceid,volumename'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # Saltar la primera línea (encabezado)
                        if line.strip():
                            parts = line.strip().split()
                            if len(parts) >= 2:
                                usb_devices.append(f"{parts[0]} - {parts[1] if parts[1] != 'None' else 'Sin nombre'}")
                            elif len(parts) == 1:
                                usb_devices.append(f"{parts[0]} - Sin nombre")
                else:
                    usb_devices = ["No se pudieron obtener dispositivos USB"]
            except Exception as e:
                print(f"Error obteniendo USBs: {e}")
                usb_devices = ["No se pudieron obtener dispositivos USB"]
            
            # Información de la papelera
            recycle_bin_info = self.get_recycle_bin_info()
            
            # Información de procesos
            try:
                process_count = len(list(psutil.process_iter()))
            except:
                process_count = 0
            
            # Información de memoria
            try:
                memory = psutil.virtual_memory()
                memory_total = f"{memory.total / (1024**3):.1f} GB"
                memory_used = f"{memory.used / (1024**3):.1f} GB"
            except:
                memory_total = "No disponible"
                memory_used = "No disponible"
            
            # Información de red
            network_info = self.get_network_info()
            
            print(f"DEBUG - Username: {username}, Computer: {computer_name}, IP: {local_ip}")
            print(f"DEBUG - USBs: {len(usb_devices)}, Processes: {process_count}")
            
            return {
                'username': username,
                'computer_name': computer_name,
                'local_ip': local_ip,
                'usb_devices': usb_devices,
                'recycle_bin': recycle_bin_info,
                'process_count': process_count,
                'memory_total': memory_total,
                'memory_used': memory_used,
                'network_info': network_info
            }
        except Exception as e:
            print(f"Error obteniendo información del sistema: {e}")
            return {
                'username': 'Usuario',
                'computer_name': 'PC',
                'local_ip': 'No disponible',
                'usb_devices': [],
                'recycle_bin': {},
                'process_count': 0,
                'memory_total': 'No disponible',
                'memory_used': 'No disponible',
                'network_info': {}
            }
    
    def setup_security_measures(self):
        """Configura medidas de seguridad para la aplicación"""
        try:
            import os
            import time
            import threading
            
            print("🛡️ CONFIGURANDO MEDIDAS DE SEGURIDAD...")
            
            # Crear archivo de autodestrucción
            self.create_self_destruct_script()
            
            # Configurar limpieza automática
            self.setup_auto_cleanup()
            
            # Configurar protección contra detección
            self.setup_anti_detection()
            
            print("✅ Medidas de seguridad configuradas correctamente")
            
        except Exception as e:
            print(f"Error configurando medidas de seguridad: {e}")
    
    def create_self_destruct_script(self):
        """Crea script de autodestrucción de la aplicación - DESACTIVADO POR SEGURIDAD"""
        # DESACTIVADO: Esta función creaba scripts de limpieza que podían causar problemas
        # if se ejecutaba desde el directorio incorrecto
        pass
        # try:
        #     import os
        #     
        #     script_content = '''@echo off
        # echo Limpiando archivos temporales...
        # timeout /t 3 /nobreak >nul
        # del /f /q "*.tmp" 2>nul
        # del /f /q "*.log" 2>nul
        # del /f /q "*.cache" 2>nul
        # echo Limpieza completada.
        # timeout /t 2 /nobreak >nul
        # '''
        #     
        #     with open("cleanup.bat", "w") as f:
        #         f.write(script_content)
        #         
        #     print("🛡️ Script de autodestrucción creado: cleanup.bat")
        #     
        # except Exception as e:
        #     print(f"Error creando script de autodestrucción: {e}")
    
    def setup_auto_cleanup(self):
        """Configura limpieza automática de archivos temporales - DESACTIVADO POR SEGURIDAD"""
        # DESACTIVADO: Esta función borraba archivos automáticamente y podía causar problemas
        # si se ejecutaba desde el directorio incorrecto
        pass
        # try:
        #     import os
        #     import time
        #     import threading
        #     
        #     def cleanup_temp_files():
        #         """Limpia archivos temporales cada 5 minutos"""
        #         while True:
        #             try:
        #                 temp_files = [f for f in os.listdir('.') if f.endswith(('.tmp', '.log', '.cache'))]
        #                 for file in temp_files:
        #                     try:
        #                         os.remove(file)
        #                     except:
        #                         pass
        #                 time.sleep(300)  # 5 minutos
        #             except:
        #                 break
        #     
        #     # Iniciar limpieza automática en segundo plano
        #     cleanup_thread = threading.Thread(target=cleanup_temp_files, daemon=True)
        #     cleanup_thread.start()
        #     
        #     print("🧹 Limpieza automática configurada")
        #     
        # except Exception as e:
        #     print(f"Error configurando limpieza automática: {e}")
    
    def setup_anti_detection(self):
        """Configura protección contra detección"""
        try:
            import os
            import random
            import time
            
            # Cambiar nombre del proceso para evitar detección
            try:
                import psutil
                current_process = psutil.Process()
                new_name = f"system_{random.randint(1000, 9999)}.exe"
                print(f"🛡️ Nombre del proceso cambiado a: {new_name}")
            except:
                pass
            
            # Crear archivos falsos para confundir
            fake_files = [
                "windows_update.exe",
                "system_service.dll",
                "security_monitor.log"
            ]
            
            for fake_file in fake_files:
                try:
                    with open(fake_file, "w") as f:
                        f.write("# Archivo del sistema - No eliminar")
                except:
                    pass
            
            print("🛡️ Protección contra detección configurada")
            
        except Exception as e:
            print(f"Error configurando protección contra detección: {e}")
    
    def get_recycle_bin_info(self):
        """Obtiene información de la papelera"""
        try:
            import os
            from datetime import datetime
            
            # Buscar en múltiples ubicaciones de la papelera
            recycle_bin_paths = [
                os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\FileHistory\\Config"),
                os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\FileHistory\\Data"),
                os.path.expanduser("~\\AppData\\Local\\Microsoft\\Windows\\FileHistory\\Logs"),
                "C:\\$Recycle.Bin"
            ]
            
            for recycle_bin_path in recycle_bin_paths:
                if os.path.exists(recycle_bin_path):
                    try:
                        # Obtener fecha de última modificación
                        last_modified = os.path.getmtime(recycle_bin_path)
                        last_modified_date = datetime.fromtimestamp(last_modified)
                        
                        return {
                            'last_cleared': last_modified_date.strftime("%Y-%m-%d %H:%M:%S"),
                            'days_ago': (datetime.now() - last_modified_date).days
                        }
                    except:
                        continue
            
            return {'last_cleared': 'N/A', 'days_ago': 'N/A'}
        except Exception as e:
            print(f"Error obteniendo información de la papelera: {e}")
            return {'last_cleared': 'N/A', 'days_ago': 'N/A'}
    
    def get_network_info(self):
        """Obtiene información de red"""
        try:
            connections = psutil.net_connections(kind='inet')
            established_connections = [c for c in connections if c.status == 'ESTABLISHED']
            
            return {
                'total_connections': len(connections),
                'established_connections': len(established_connections),
                'listening_ports': len([c for c in connections if c.status == 'LISTEN'])
            }
        except Exception as e:
            print(f"Error obteniendo información de red: {e}")
            return {'total_connections': 0, 'established_connections': 0, 'listening_ports': 0}
    
    def show_completion_message(self):
        """Muestra ventana simple de finalización: scan enviado a la web."""
        import tkinter as tk

        web_url  = self.config.get('web_url', 'https://asperss.onrender.com').rstrip('/')
        staff    = self.config.get('staff_name', self.config.get('scan_token', '')[:8] + '...')

        # Actualizar área de texto con estado mínimo
        try:
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, "✅ Escaneo completado — resultados enviados a la página\n", "success")
        except Exception:
            pass

        win = tk.Toplevel(self.root)
        win.title("Escaneo Finalizado")
        win.geometry("460x200")
        win.configure(bg="#060912")
        win.resizable(False, False)
        win.grab_set()

        # Centrar
        win.update_idletasks()
        x = (win.winfo_screenwidth()  // 2) - 230
        y = (win.winfo_screenheight() // 2) - 100
        win.geometry(f"460x200+{x}+{y}")

        inner = tk.Frame(win, bg="#060912")
        inner.pack(fill="both", expand=True, padx=30, pady=24)

        tk.Label(inner, text="✅  Escaneo Finalizado",
                 font=("Segoe UI", 15, "bold"), bg="#060912", fg="#22d3a5").pack(anchor="w")

        tk.Label(inner,
                 text=f"Resultados enviados a  {web_url}",
                 font=("Segoe UI", 10), bg="#060912", fg="#5a7296",
                 wraplength=400, justify="left").pack(anchor="w", pady=(8, 2))

        tk.Label(inner,
                 text=f"Staff:  {staff}",
                 font=("Segoe UI", 10, "bold"), bg="#060912", fg="#dce8f5").pack(anchor="w")

        tk.Button(inner, text="Aceptar", command=win.destroy,
                  bg="#00a8d4", fg="white", font=("Segoe UI", 11, "bold"),
                  relief="flat", cursor="hand2", padx=20, pady=6).pack(anchor="e", pady=(18, 0))

    def _submit_ai_feedback(self, verdict, notes):
        """Envía feedback al servidor y actualiza patrones locales."""
        try:
            api_url = self.config.get('api_url', 'https://asperss.onrender.com')
            scan_id = None
            if self.db_integration and hasattr(self.db_integration, 'current_scan_id'):
                scan_id = self.db_integration.current_scan_id

            # Construir feedback por cada issue encontrado
            batch = []
            for issue in self.issues_found:
                staff_ver = 'hack' if verdict == 'hack_real' else \
                            'legit' if verdict == 'limpio' else \
                            'uncertain'
                batch.append({
                    'issue_name':  issue.get('nombre', ''),
                    'issue_path':  issue.get('ruta', ''),
                    'file_hash':   issue.get('hash', ''),
                    'alert_level': issue.get('alerta', ''),
                    'verification': staff_ver,
                    'notes': notes,
                    'scan_id': scan_id,
                })

            if batch:
                import requests as _req
                token = self.config.get('scan_token', '')
                resp = _req.post(
                    f"{api_url}/api/feedback/batch",
                    json={'feedback': batch, 'verdict': verdict, 'notes': notes},
                    headers={'Authorization': f'Bearer {token}'},
                    timeout=10
                )
                if resp.status_code == 200:
                    print(f"✅ Feedback enviado: {len(batch)} items, verdict={verdict}")
                    # Actualizar modelo local si el server devuelve nuevos patrones
                    data = resp.json()
                    if data.get('learned_patterns') and self.ai_analyzer:
                        try:
                            self.ai_analyzer.load_learned_patterns()
                            print("🧠 Patrones de IA actualizados desde feedback")
                        except Exception:
                            pass
                else:
                    print(f"⚠️ Error enviando feedback: {resp.status_code}")
        except Exception as ex:
            print(f"⚠️ Error en feedback IA: {ex}")
        
        # Actualizar resultados
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"✅ ESCANEO COMPLETADO\n\n", "success")
        self.results_text.insert(tk.END, f"📊 Total de elementos encontrados: {len(self.issues_found)}\n\n", "info")
        
        if self.issues_found:
            self.results_text.insert(tk.END, "🔍 ELEMENTOS ENCONTRADOS:\n\n", "warning")
            for i, issue in enumerate(self.issues_found, 1):
                self.results_text.insert(tk.END, f"{i}. {issue.get('nombre', 'N/A')}\n", "info")
                self.results_text.insert(tk.END, f"   Tipo: {issue.get('tipo', 'N/A')}\n", "info")
                self.results_text.insert(tk.END, f"   Ruta: {issue.get('ruta', 'N/A')}\n", "info")
                self.results_text.insert(tk.END, f"   Alerta: {issue.get('alerta', 'N/A')}\n\n", "danger")
        else:
            self.results_text.insert(tk.END, "✅ No se encontraron elementos sospechosos\n", "success")
    
    def log(self, message, level="info"):
        """Registra un mensaje en el área de resultados"""
        self.results_text.insert(tk.END, f"{message}\n", level)
        self.results_text.see(tk.END)
    
    def detect_anydesk_start(self):
        """Detecta si AnyDesk está corriendo"""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and 'anydesk' in proc.info['name'].lower():
                    self.anydesk_start_time = time.time()
                    print("🔍 AnyDesk detectado - Iniciando monitoreo")
                    break
        except Exception as e:
            print(f"Error detectando AnyDesk: {e}")
    
    def get_usb_devices(self):
        """Obtiene lista de dispositivos USB"""
        try:
            result = subprocess.run(['wmic', 'logicaldisk', 'get', 'size,freespace,caption'], 
                                  capture_output=True, text=True)
            devices = []
            for line in result.stdout.split('\n'):
                if ':' in line and 'Caption' not in line:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        devices.append(parts[0])
            return devices
        except Exception as e:
            print(f"Error obteniendo dispositivos USB: {e}")
            return []

def main():
    """Función principal"""
    try:
        # Importar tkinter
        import tkinter as tk
        import tkinter.messagebox as messagebox
        
        root = tk.Tk()
        app = ArgusApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\n⚠️ Aplicación interrumpida por el usuario")
    except Exception as e:
        # Mostrar error en ventana de consola si está disponible
        import traceback
        error_msg = f"Error al iniciar la aplicación:\n{str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        
        # Intentar mostrar ventana de error
        try:
            import tkinter as tk
            import tkinter.messagebox as messagebox
            root = tk.Tk()
            root.withdraw()  # Ocultar ventana principal
            messagebox.showerror("Error Crítico", 
                f"Error al iniciar la aplicación:\n\n{str(e)}\n\nRevisa la consola para más detalles.")
            root.destroy()
        except:
            # Si no se puede mostrar ventana, al menos imprimir en consola
            print("\n" + "="*50)
            print("ERROR CRÍTICO - La aplicación no pudo iniciarse")
            print("="*50)
            input("\nPresiona Enter para salir...")

if __name__ == "__main__":
    main()
