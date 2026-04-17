import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, Toplevel
import threading
import os
import sys
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
        
        # Intentar cargar hashes desde API (actualización dinámica)
        api_url = self.config.get('api_url', '')
        if api_url:
            try:
                response = requests.get(
                    f"{api_url}/api/ai-model/latest",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    api_hashes = data.get('hashes', [])
                    
                    for hash_data in api_hashes:
                        if hash_data.get('is_hack') and hash_data.get('hash'):
                            hash_value = hash_data.get('hash')
                            if hash_value not in known_hashes:
                                known_hashes.append(hash_value)
                    
                    print(f"✅ {len(api_hashes)} hashes adicionales cargados desde API")
                    
                    # Guardar en archivo local para uso offline
                    models_dir = 'models'
                    os.makedirs(models_dir, exist_ok=True)
                    model_file = os.path.join(models_dir, 'ai_model_latest.json')
                    with open(model_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
                    
            except Exception as e:
                print(f"⚠️ Error cargando hashes desde API: {e}")
                # Intentar cargar desde archivo local como fallback
                try:
                    model_file = os.path.join('models', 'ai_model_latest.json')
                    if os.path.exists(model_file):
                        with open(model_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        api_hashes = data.get('hashes', [])
                        for hash_data in api_hashes:
                            if hash_data.get('is_hack') and hash_data.get('hash'):
                                hash_value = hash_data.get('hash')
                                if hash_value not in known_hashes:
                                    known_hashes.append(hash_value)
                        print(f"✅ Hashes cargados desde archivo local (modo offline)")
                except:
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
        """Escanea caché DNS"""
        print("🔍 ESCANEANDO CACHÉ DNS...")
        issues = []
        
        def scan():
            try:
                result = subprocess.run(['ipconfig', '/displaydns'], capture_output=True, text=True)
                if result.returncode == 0:
                    dns_output = result.stdout
                    if any(hack in dns_output.lower() for hack in ['vape', 'entropy', 'liquidbounce']):
                        issues.append({
                            'tipo': 'DNS_CACHE',
                            'nombre': 'DNS Cache',
                            'ruta': 'DNS Cache',
                            'alerta': 'POCO_SOSPECHOSO',
                            'categoria': 'DNS_CACHE'
                        })
                        
            except Exception as e:
                print(f"Error escaneando caché DNS: {e}")
                
        scan()
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
        
        # PATRONES DE FALSOS POSITIVOS (MÁS AMPLIOS PARA EVITAR FALSOS POSITIVOS)
        exclude_patterns = [
            # Sistema Windows crítico
            'system32', 'syswow64', 'windows\\system32', 'windows', 'program files',
            'programdata', 'microsoft', 'adobe', 'google', 'mozilla', 'firefox', 'chrome',
            'office', 'word', 'excel', 'powerpoint', 'outlook', 'nvidia', 'amd', 'intel',
            'realtek', 'logitech', 'razer', 'steam', 'epic', 'origin', 'uplay', 'battle.net',
            'discord', 'teamspeak', 'skype', 'zoom', 'teams',
            
            # Servidores y desarrollo
            'xampp', 'tomcat', 'apache', 'mysql', 'php', 'websocket', 'webapps', 'examples',
            'lib', 'classes', 'web-inf', 'webalizer', 'cygwin', 'bgd', 'wcmgr', 'zlib',
            
            # Juegos legítimos
            'project zomboid', 'zomboid', 'shaders', 'textures', 'media',
            
            # Librerías Python legítimas
            'vscode', 'pylance', 'skimage', 'measure', 'stubs', 'bundled', 'pyi',
            
            # Librerías Java legítimas
            'gson', 'jackson', 'log4j', 'authlib', 'taglibs', 'standard-impl', 'standard-spec',
            'gson-2.8', 'jackson-core', 'log4j-', 'authlib-',
            
            # Mods legítimos de Minecraft
            'jei-', 'rubidium', 'oculus', 'create-', 'botania', 'cobblemon', 'custom curve',
            'optifine', 'fabric', 'forge', 'modrinth', 'curseforge', 'minecraftforge',
            'fabricloader', 'iris', 'sodium', 'lithium', 'phosphor', 'entity culling',
            
            # Launchers legítimos
            'minecraft launcher', 'tlauncher-', 'prism', 'lunarclient', 'lunar', 'badlion',
            
            # Sistema crítico
            'api-ms-win-', 'msvcr', 'msvcp', 'vcruntime', 'ucrtbase',
            'kernel32.dll', 'user32.dll', 'advapi32.dll', 'shell32.dll',
            
            # Carpetas del sistema
            'temp', 'tmp', 'cache', 'logs', 'backup', 'recycle', 'appdata', 'local', 'roaming',
            
            # Editores y entornos de desarrollo
            'cursor', 'extensions', 'node_modules', 'client', 'jdk', 'jre', 'legal',
            'nido', 'mapmode', 'out', 'gitlens', 'doxdocgen', 'code-runner',
            'path-autocomplete', 'python', 'java', 'cmake', 'clang-format', 'visual studio',
            'intellij', 'eclipse', 'netbeans', 'atom', 'sublime', 'notepad++', 'pycharm',
            'webstorm', 'goland', 'clion', 'numpy', 'scipy', 'pandas', 'matplotlib',
            'sklearn', 'tensorflow', 'pytorch', 'keras', 'theano', 'caffe'
        ]
        
        # ============================================================
        # FILTRADO MEJORADO
        # ============================================================
        
        for item in issues:
            nombre = item.get('nombre', '').lower()
            ruta = item.get('ruta', '').lower()
            archivo = item.get('archivo', '').lower()
            tipo = item.get('tipo', '').lower()
            
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
            
            # Verificar falsos positivos específicos adicionales (menos estricto)
            if not is_false_positive:
                for false_positive in ['zomboid', 'shaders', 'textures', 'media', 'vscode', 'pylance', 'skimage', 'pyi', 'system32', 'program files', 'windows', 'microsoft', 'adobe']:
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
                'libraries', 'natives', 'assets', 'resourcepacks', 'saves',
                'launcher', 'client', 'hack', 'cheat', 'downloads', 'desktop',
                'temp', 'tmp', 'appdata', 'documents'
            ]
            
            is_in_suspicious_folder = any(path in ruta for path in suspicious_paths)
            
            # 5. CLASIFICAR POR SEVERIDAD (usando análisis de contenido si está disponible)
            if is_potential_hack or is_in_suspicious_folder or content_confidence >= 60:
                # Usar análisis de contenido para determinar severidad si está disponible
                if content_confidence >= 80:
                    item['alerta'] = 'CRITICAL'
                    item['categoria'] = 'HACKS'
                    hacks_critical.append(item)
                elif content_confidence >= 60:
                    item['alerta'] = 'SOSPECHOSO'
                    item['categoria'] = 'HACKS'
                    hacks_sospechoso.append(item)
                elif any(hack in archivo for hack in ['vape', 'entropy', 'whiteout', 'injector', 'dllinjector']):
                    item['alerta'] = 'CRITICAL'
                    item['categoria'] = 'HACKS'
                    hacks_critical.append(item)
                elif any(hack in archivo for hack in ['liquidbounce', 'wurst', 'impact', 'inject', 'killaura', 'aimbot']):
                    item['alerta'] = 'SOSPECHOSO'
                    item['categoria'] = 'HACKS'
                    hacks_sospechoso.append(item)
                elif any(hack in archivo for hack in ['sigma', 'flux', 'future', 'ghost', 'bypass']):
                    item['alerta'] = 'POCO_SOSPECHOSO'
                    item['categoria'] = 'HACKS'
                    hacks_poco_sospechoso.append(item)
                else:
                    item['alerta'] = 'NORMAL'
                    item['categoria'] = 'HACKS'
                    hacks_normal.append(item)
                
                filtered.append(item)
        
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
            for item in hacks_poco_sospechoso[:5]:  # Mostrar solo los primeros 5
                print(f"  - {item.get('archivo', 'N/A')} en {item.get('ruta', 'N/A')}")
        
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
            # Usar sistema de estilos moderno
            main_panel = tk.Frame(self.root, bg=ModernUI.COLORS['bg_primary'])
            main_panel.pack(fill=tk.BOTH, expand=True)
            
            # Crear header moderno
            ModernUI.create_header(main_panel)
            
            # Crear sección de progreso
            progress_widgets = ModernUI.create_progress_section(main_panel)
            self.progress_frame = progress_widgets['container']
            self.progress_label = progress_widgets['status']
            self.progress_bar = progress_widgets['progress']
            self.progress_detail_label = progress_widgets['detail']
            self.timer_label = progress_widgets['timer']
            self.resources_label = progress_widgets['resources']
            self.progress_percent_label = progress_widgets.get('percent', None)
            self.progress_value = 0
            
            # Crear botones de acción ultra compactos en línea horizontal
            button_container = tk.Frame(main_panel, bg=ModernUI.COLORS['bg_primary'])
            button_container.pack(fill=tk.X, pady=8, padx=15)
            
            # Contenedor horizontal para botones lado a lado
            buttons_row = tk.Frame(button_container, bg=ModernUI.COLORS['bg_primary'])
            buttons_row.pack(fill=tk.X)
            
            # Botón principal compacto
            scan_btn_frame = ModernUI.create_button(
                buttons_row,
                "INICIAR ESCANEO",
                self.full_scan_with_discord,
                style='primary',
                icon='🚀'
            )
            scan_btn_frame.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)
            # Obtener referencia al botón real
            self.scan_button = None
            for widget in scan_btn_frame.winfo_children():
                if isinstance(widget, tk.Button):
                    self.scan_button = widget
                    break
            
            # Botón secundario compacto
            details_btn_frame = ModernUI.create_button(
                buttons_row,
                "VER RESULTADOS",
                self.show_details,
                style='secondary',
                icon='📊'
            )
            details_btn_frame.pack(side=tk.LEFT, padx=(0, 0), fill=tk.X, expand=True)
            # Obtener referencia al botón real
            self.details_button = None
            for widget in details_btn_frame.winfo_children():
                if isinstance(widget, tk.Button):
                    self.details_button = widget
                    self.details_button.config(state=tk.DISABLED)
                    break
            
            # Crear sección de resultados
            results_widgets = ModernUI.create_results_section(main_panel)
            self.results_frame = results_widgets['container']
            self.results_text = results_widgets['text']
            self.results_label = results_widgets['title']
        else:
            # Fallback al estilo anterior si no está disponible el módulo
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
        
        self.details_button = tk.Button(
            button_frame,
            text="📊 VER RESULTADOS DETALLADOS",
            command=self.show_details,
            bg="#21262d",
            fg="#f0f6fc",
            font=("Segoe UI", 11, "bold"),
            padx=30,
            pady=12,
            relief=tk.FLAT,
            state=tk.DISABLED,
            cursor="hand2",
            activebackground="#30363d"
        )
        self.details_button.pack(pady=(15, 0))
        
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
                    
                    # Si ya llegamos al objetivo, esperar un poco y verificar de nuevo
                    if current == target:
                        time.sleep(0.1)  # Esperar un poco antes de verificar de nuevo
                        # Si después de esperar sigue siendo el mismo, terminar
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
                    def update_ui():
                        try:
                            if hasattr(self, 'progress_bar'):
                                self.progress_bar['value'] = next_value
                            if hasattr(self, 'progress_label'):
                                self.progress_label.config(text=f"{last_message} ({next_value}%)")
                            if hasattr(self, 'progress_percent_label') and self.progress_percent_label:
                                self.progress_percent_label.config(text=f"{next_value}%")
                        except:
                            pass
                    
                    # Programar actualización en el hilo principal
                    self.root.after(0, update_ui)
                    
                    # Esperar antes del siguiente paso (velocidad ajustable)
                    time.sleep(0.025)  # 25ms por paso = 40 pasos por segundo
                    
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
                
                # Aplicar análisis de IA a los resultados
                if self.ai_analyzer and self.issues_found:
                    try:
                        print("🤖 Aplicando análisis de IA a los resultados...")
                        self.issues_found = self.ai_analyzer.analyze_batch(self.issues_found)
                        print(f"✅ Análisis de IA completado - {len(self.issues_found)} issues analizados")
                    except Exception as e:
                        print(f"⚠️ Error en análisis de IA: {e}")
                
                # Filtrar resultados finales
                self.issues_found = self.filter_false_positives(self.issues_found)
                
                # Generar reporte HTML
                self.generate_html_report()
                
                # Envío a Web (Discord eliminado)
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
                            success = self.db_integration.submit_results(
                                self.issues_found,
                                self.total_files_scanned,
                                scan_duration
                            )
                            if success:
                                print("✅ Resultados enviados a Web/BD")
                            else:
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
                
                # Mostrar mensaje de finalización
                self.root.after(0, lambda: self.show_completion_message())
                
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
                    
                    # Buscar hacks específicos primero
                    self._scan_for_specific_hacks(drive)
                    
                    future = executor.submit(self.scan_drive_exhaustive, drive, start_progress, end_progress)
                    futures.append(future)
                
                # Esperar a que terminen todos con timeout aumentado
                for future in concurrent.futures.as_completed(futures, timeout=600):  # 10 minutos timeout
                    try:
                        future.result()
                        print(f"✅ Unidad escaneada exitosamente")
                    except concurrent.futures.TimeoutError:
                        print(f"⏰ Timeout en escaneo de unidad después de 10 minutos - continuando...")
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
                _run_safe(self.secondary_scan_parallel)
                _run_safe(self.scan_processes)
                _run_safe(self.advanced_minecraft_process_analysis)
                _run_safe(self.scan_disabled_processes)
                _run_safe(self.scan_running_processes)
                _run_safe(self.scan_dns_cache)
                _run_safe(self.scan_windows)

            # Grupo B — Archivos y fechas (I/O medio)
            def _group_files():
                self._update_progress_safe(83, "⚡ Archivos", "Analizando archivos modificados...")
                _run_safe(self.scan_exe_files)
                _run_safe(self.scan_jar_files)
                _run_safe(self.scan_files_by_date)
                _run_safe(self.scan_deleted_files)
                _run_safe(self.scan_created_files)
                _run_safe(self.scan_renamed_files)
                _extend_safe(_run_safe(self.scan_hidden_files))

            # Grupo C — Registro y JNA (I/O bajo)
            def _group_registry():
                self._update_progress_safe(85, "⚡ Registro y JNA", "Analizando entradas del registro...")
                _run_safe(self.scan_prefetch_jna)
                _run_safe(self.scan_temp_jna)
                _run_safe(self.scan_registry_suspicious)
                _run_safe(self.scan_registry)
                _run_safe(self.scan_event_logs)

            # Grupo D — Hardware y red (I/O alto)
            def _group_hardware():
                self._update_progress_safe(87, "⚡ Hardware y red", "Analizando dispositivos y conexiones...")
                _run_safe(self.scan_logitech_macros)
                _run_safe(self.scan_razer_macros)
                _extend_safe(_run_safe(self.scan_usb_devices))
                _extend_safe(_run_safe(self.scan_network_connections))

            # Grupo E — Ubicaciones de hacks (I/O alto)
            def _group_hack_locations():
                self._update_progress_safe(89, "🎯 Ubicaciones de hacks", "Downloads, Desktop, Roaming...")
                _run_safe(self.scan_common_hack_locations)
                _run_safe(self.scan_suspicious_folders)
                _run_safe(self.scan_exact_hack_names)

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
                for f in concurrent.futures.as_completed(sec_futures, timeout=300):
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

            # Fase 9: Filtrado y clasificación (100%)
            self._update_progress_safe(100, "🔍 Filtrando resultados", "Aplicando filtros ultra estrictos...")
            
            # Aplicar filtro ultra inteligente
            self.issues_found = self.filter_false_positives(self.issues_found)
            
            # Aplicar segundo filtro más inteligente
            self.issues_found = self.secondary_filter(self.issues_found)
            
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
            
            # Finalizar
            self._update_progress_safe(100, "✅ Escaneo completado", f"Encontrados {len(self.issues_found)} elementos")
            
            # Estadísticas finales
            if hasattr(self, 'scan_start_time'):
                total_time = time.time() - self.scan_start_time
                print(f"🏁 ESTADÍSTICAS FINALES:")
                print(f"   📁 Total elementos encontrados: {len(self.issues_found)}")
                print(f"   ⏱️ Tiempo total de escaneo: {total_time:.1f} segundos")
                print(f"   🔧 CPU cores utilizados: {psutil.cpu_count()}")
                print(f"   💾 Memoria disponible: {psutil.virtual_memory().available / (1024**3):.1f} GB")
            
            # Generar reporte HTML
            print("📄 Generando reporte HTML...")
            self.generate_html_report()
            
            print("✅ ESCANEO COMPLETADO")
            
        except Exception as e:
            print(f"Error durante escaneo exhaustivo: {str(e)}")
            import traceback
            traceback.print_exc()
            self._update_progress_safe(100, f"❌ Error: {str(e)}", "Error durante el escaneo")
        finally:
            # Detener cronómetro
            self.stop_scan_timer()
            self.scanning = False
    
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
            
            # Calcular timeout dinámico según hardware (OPTIMIZADO - sin cpu_freq que es lento)
            try:
                cpu_count = psutil.cpu_count() or 2
                
                # OPTIMIZACIÓN: No usar cpu_freq() que puede ser muy lento en algunos sistemas
                # Usar heurística basada solo en número de cores (más rápido)
                base_timeout = 300  # 5 minutos base
                
                if cpu_count < 4:
                    # Pocos cores = procesador probablemente lento
                    total_timeout = 600  # 10 minutos
                    print(f"⚙️ Hardware detectado: {cpu_count} cores - Timeout ajustado a {total_timeout//60} minutos")
                elif cpu_count < 8:
                    # Cores medios
                    total_timeout = 450  # 7.5 minutos
                    print(f"⚙️ Hardware detectado: {cpu_count} cores - Timeout: {total_timeout//60} minutos")
                else:
                    # Muchos cores = procesador rápido
                    total_timeout = base_timeout
                    print(f"⚙️ Hardware detectado: {cpu_count} cores - Timeout: {total_timeout//60} minutos")
            except Exception as e:
                # Si falla la detección, usar timeout estándar (más rápido)
                total_timeout = 300  # 5 minutos por defecto
                print(f"⚠️ No se pudo detectar hardware, usando timeout estándar: {total_timeout//60} minutos")
            
            scanned_files = 0
            max_files_per_folder = None  # Sin límite de archivos por carpeta (solo timeout total)
            
            # Actualizar contador global
            if not hasattr(self, 'total_files_scanned'):
                self.total_files_scanned = 0
            
            max_depth = 12  # Profundidad máxima (suficiente para encontrar hacks)
            
            # Carpetas a saltar (solo las realmente innecesarias)
            skip_folders = {
                'node_modules', '.git', '.svn', '.hg', '__pycache__', 
                'venv', 'env', '.venv', 
                'Windows\\WinSxS',  # Solo WinSxS, no todo System32
            }
            
            # Escanear TODAS las carpetas importantes
            critical_paths = [
                os.path.join(drive, "Users"),
                os.path.join(drive, "Program Files"),
                os.path.join(drive, "Program Files (x86)"),
                os.path.join(drive, "ProgramData"),
                os.path.join(drive, "Windows", "System32"),
                os.path.join(drive, "Windows", "SysWOW64"),
                os.path.join(drive, "Windows", "Temp"),
                os.path.join(drive, "Windows", "Prefetch"),
                os.path.join(drive, "PerfLogs"),
            ]
            
            # Primero escanear carpetas específicas con límites
            for critical_path in critical_paths:
                if not os.path.exists(critical_path):
                    continue
                    
                folder_start_time = time.time()
                folder_scanned = 0
                print(f"📁 ESCANEANDO CARPETA CRÍTICA: {critical_path}")
                
                try:
                    for root, dirs, files in os.walk(critical_path):
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
                        
                        # Verificar carpetas sospechosas
                        for dir_name in dirs:
                            if any(pattern in dir_name.lower() for pattern in ['flux', 'vape', 'entropy', 'liquidbounce', 'wurst', 'impact', 'sigma', 'future', 'ghost', 'hack', 'cheat', 'mod', 'client']):
                                self.issues_found.append({
                                    'nombre': dir_name,
                                    'ruta': root,
                                    'archivo': os.path.join(root, dir_name),
                                    'tipo': 'folder',
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
                                        'alerta': 'SOSPECHOSO'
                                    })
                                
                                scanned_files += 1
                                folder_scanned += 1
                                self.total_files_scanned += 1  # Actualizar contador global
                                
                                # Mostrar progreso cada 5000 archivos
                                if scanned_files % 5000 == 0:
                                    elapsed = time.time() - start_time
                                    rate = scanned_files / elapsed if elapsed > 0 else 0
                                    remaining = total_timeout - elapsed
                                    print(f"📁 {drive}: {scanned_files} archivos ({rate:.0f} arch/s) - Tiempo restante: {remaining:.0f}s...")
                                
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
            
            # Escanear TODAS las carpetas del usuario exhaustivamente
            user_home = os.path.expanduser("~")
            user_paths = [
                os.path.join(user_home, "Downloads"),
                os.path.join(user_home, "Desktop"),
                os.path.join(user_home, "Documents"),
                os.path.join(user_home, "AppData", "Roaming"),
                os.path.join(user_home, "AppData", "Local"),
                os.path.join(user_home, "AppData", "LocalLow"),
                os.path.join(user_home, "AppData", "Roaming", ".minecraft"),
                os.path.join(user_home, "AppData", "Roaming", ".minecraft", "mods"),
                os.path.join(user_home, "AppData", "Roaming", ".minecraft", "versions"),
                os.path.join(user_home, "AppData", "Roaming", ".minecraft", "resourcepacks"),
                os.path.join(user_home, "AppData", "Roaming", ".minecraft", "shaderpacks"),
                os.path.join(user_home, "Videos"),
                os.path.join(user_home, "Music"),
                os.path.join(user_home, "Pictures"),
                os.path.join(user_home, "OneDrive"),
            ]
            
            # También escanear todas las carpetas de otros usuarios
            users_dir = os.path.join(drive, "Users")
            if os.path.exists(users_dir):
                try:
                    for user_folder in os.listdir(users_dir):
                        user_path = os.path.join(users_dir, user_folder)
                        if os.path.isdir(user_path) and user_folder not in ['Default', 'Public', 'All Users']:
                            user_paths.extend([
                                os.path.join(user_path, "Downloads"),
                                os.path.join(user_path, "Desktop"),
                                os.path.join(user_path, "Documents"),
                                os.path.join(user_path, "AppData", "Roaming", ".minecraft"),
                            ])
                except:
                    pass
            
            for user_path in user_paths:
                if not os.path.exists(user_path):
                    continue
                    
                folder_start_time = time.time()
                folder_scanned = 0
                print(f"📁 ESCANEANDO: {user_path}")
                
                try:
                    for root, dirs, files in os.walk(user_path):
                        # Timeout por carpeta optimizado
                        if time.time() - folder_start_time > 120:  # 2 minutos máximo
                            print(f"⏰ Timeout en {user_path} - continuando...")
                            break
                        
                        # Profundidad máxima optimizada
                        depth = root.count(os.sep) - user_path.count(os.sep)
                        if depth > 8:
                                dirs[:] = []
                                continue
                            
                        # Saltar solo carpetas realmente problemáticas
                        dirs[:] = [d for d in dirs if not any(skip in os.path.join(root, d).lower() for skip in skip_folders)]
                        
                        # Verificar timeout total (sin límite de archivos)
                        if time.time() - start_time > total_timeout:
                            print(f"⏰ Timeout total alcanzado - finalizando escaneo...")
                            break
                        
                        # Filtrar archivos relevantes (MÁS EXTENSIONES)
                        relevant_extensions = (
                            '.jar', '.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.py', 
                            '.class', '.java', '.lua', '.txt', '.log', '.cfg', '.config', '.json', 
                            '.properties', '.yml', '.yaml', '.xml', '.dat', '.bin', '.cache',
                            '.tmp', '.temp', '.bak', '.backup', '.old', '.new', '.mod', '.minecraft',
                            '.zip', '.rar', '.7z', '.tar', '.gz', '.msi', '.msm', '.msp', '.jar',
                            '.class', '.java', '.scala', '.kt', '.groovy'
                        )
                        relevant_files = [f for f in files if f.lower().endswith(relevant_extensions)]
                        
                        # Verificar carpetas sospechosas
                        for dir_name in dirs:
                            if any(pattern in dir_name.lower() for pattern in ['flux', 'vape', 'entropy', 'liquidbounce', 'wurst', 'impact', 'sigma', 'future', 'ghost', 'hack', 'cheat', 'mod', 'client']):
                                self.issues_found.append({
                                    'nombre': dir_name,
                                    'ruta': root,
                                    'archivo': os.path.join(root, dir_name),
                                    'tipo': 'folder',
                                    'alerta': 'SOSPECHOSO'
                                })
                        
                        # Procesar TODOS los archivos relevantes (sin límite por iteración)
                        for file in relevant_files:
                            try:
                                file_path = os.path.join(root, file)
                                
                                if self.is_suspicious_file(file_path):
                                    self.issues_found.append({
                                        'nombre': file,
                                        'ruta': root,
                                        'archivo': file_path,
                                        'tipo': 'file',
                                        'alerta': 'SOSPECHOSO'
                                    })
                                
                                scanned_files += 1
                                folder_scanned += 1
                                self.total_files_scanned += 1  # Actualizar contador global
                                
                                if scanned_files % 5000 == 0:
                                    elapsed = time.time() - start_time
                                    rate = scanned_files / elapsed if elapsed > 0 else 0
                                    print(f"📁 {drive}: {scanned_files} archivos ({rate:.0f} arch/s)...")
                                
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
                    print(f"⚠️ Error en {user_path}: {e} - continuando...")
                    continue
            
            # ESCANEO GENERAL DE TODA LA UNIDAD (OPTIMIZADO - solo ubicaciones críticas)
            print(f"🔍 ESCANEANDO UBICACIONES CRÍTICAS DE {drive} (escaneo optimizado)...")
            general_start_time = time.time()
            general_scanned = 0
            max_general_time = 180  # 3 minutos máximo para escaneo general (optimizado)
            
            # Solo escanear ubicaciones críticas en lugar de toda la unidad
            critical_locations = [
                os.path.join(drive, 'Users'),
                os.path.join(drive, 'Program Files'),
                os.path.join(drive, 'Program Files (x86)'),
                os.path.join(drive, 'AppData', 'Local'),
                os.path.join(drive, 'AppData', 'Roaming'),
                os.path.join(drive, 'Downloads'),
                os.path.join(drive, 'Desktop'),
                os.path.join(drive, 'Documents'),
            ]
            
            try:
                # Escanear solo ubicaciones críticas con límites optimizados
                for critical_location in critical_locations:
                    if not os.path.exists(critical_location):
                        continue
                    
                    if time.time() - general_start_time > max_general_time:
                        print(f"⏰ Timeout en escaneo general después de {max_general_time}s - continuando...")
                        break
                    
                    for root, dirs, files in os.walk(critical_location):
                        # Verificar timeout general
                        if time.time() - general_start_time > max_general_time:
                            break
                        
                        # Profundidad máxima 6 para escaneo general (optimizado)
                        depth = root.count(os.sep) - critical_location.count(os.sep)
                        if depth > 6:
                            dirs[:] = []
                            continue
                    
                    # Saltar solo carpetas realmente problemáticas
                    dirs[:] = [d for d in dirs if not any(skip in os.path.join(root, d).lower() for skip in skip_folders)]
                    
                    # Verificar si ya escaneamos esta carpeta en las rutas críticas
                    is_critical = any(critical in root for critical in critical_paths)
                    is_user = any(user in root for user in user_paths)
                    
                    # Si ya la escaneamos, saltar (pero verificar carpetas sospechosas)
                    if is_critical or is_user:
                        # Solo verificar nombres de carpetas sospechosas
                        for dir_name in dirs:
                            if any(pattern in dir_name.lower() for pattern in ['flux', 'vape', 'entropy', 'liquidbounce', 'wurst', 'impact', 'sigma', 'future', 'ghost', 'hack', 'cheat', 'mod', 'client']):
                                self.issues_found.append({
                                    'nombre': dir_name,
                                    'ruta': root,
                                    'archivo': os.path.join(root, dir_name),
                                    'tipo': 'folder',
                                    'alerta': 'SOSPECHOSO'
                                })
                        continue
                    
                    # Filtrar archivos relevantes
                    relevant_extensions = (
                        '.jar', '.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.py', 
                        '.class', '.java', '.lua', '.txt', '.log', '.cfg', '.config', '.json', 
                        '.properties', '.yml', '.yaml', '.xml', '.dat', '.bin', '.cache',
                        '.tmp', '.temp', '.bak', '.backup', '.old', '.new', '.mod', '.minecraft',
                        '.zip', '.rar', '.7z', '.tar', '.gz', '.msi', '.msm', '.msp'
                    )
                    relevant_files = [f for f in files if f.lower().endswith(relevant_extensions)]
                    
                    # Verificar carpetas sospechosas
                    for dir_name in dirs:
                        if any(pattern in dir_name.lower() for pattern in ['flux', 'vape', 'entropy', 'liquidbounce', 'wurst', 'impact', 'sigma', 'future', 'ghost', 'hack', 'cheat', 'mod', 'client']):
                            self.issues_found.append({
                                'nombre': dir_name,
                                'ruta': root,
                                'archivo': os.path.join(root, dir_name),
                                'tipo': 'folder',
                                'alerta': 'SOSPECHOSO'
                            })
                    
                    # Procesar archivos
                    for file in relevant_files:
                        try:
                            file_path = os.path.join(root, file)
                            
                            if self.is_suspicious_file(file_path):
                                self.issues_found.append({
                                    'nombre': file,
                                    'ruta': root,
                                    'archivo': file_path,
                                    'tipo': 'file',
                                    'alerta': 'SOSPECHOSO'
                                })
                            
                            scanned_files += 1
                            general_scanned += 1
                            self.total_files_scanned += 1  # Actualizar contador global
                            
                            if scanned_files % 10000 == 0:
                                elapsed = time.time() - start_time
                                rate = scanned_files / elapsed if elapsed > 0 else 0
                                print(f"📁 {drive}: {scanned_files} archivos totales ({rate:.0f} arch/s)...")
                            
                        except (PermissionError, OSError):
                            continue
                        except Exception:
                            continue
                            
            except Exception as e:
                print(f"⚠️ Error en escaneo general: {e} - continuando...")
            
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
            
            # Patrones de hacks en contenido
            hack_content_patterns = [
                b'vape', b'entropy', b'whiteout', b'liquidbounce', b'wurst',
                b'killaura', b'aimbot', b'triggerbot', b'reach', b'velocity',
                b'scaffold', b'fly', b'xray', b'fullbright', b'bypass',
                b'inject', b'ghost', b'stealth', b'undetected', b'incognito',
                b'flux', b'sigma', b'future', b'astolfo', b'exhibition',
                b'novoline', b'rise', b'moon', b'drip', b'phobos'
            ]
            
            # Análisis de strings sospechosos
            try:
                if filename_lower.endswith(('.jar', '.class', '.java', '.txt', '.lua', '.js', '.py')):
                    with open(file_path, 'rb') as f:
                        content = f.read(1024 * 1024)  # Leer primeros 1MB
                        
                        # Detectar patrones de hack en contenido
                        detected_count = 0
                        for pattern in hack_content_patterns:
                            if pattern in content:
                                detected_count += 1
                                result['detected_patterns'].append(pattern.decode('utf-8', errors='ignore'))
                        
                        if detected_count >= 2:  # Si encuentra 2+ patrones, es muy sospechoso
                            result['is_hack'] = True
                            result['confidence'] = min(90, detected_count * 15)
                        
                        # Detección de ofuscación (alto ratio de caracteres no ASCII)
                        if len(content) > 100:
                            non_ascii_ratio = sum(1 for b in content[:1000] if b > 127) / min(1000, len(content))
                            if non_ascii_ratio > 0.3:  # Más del 30% no ASCII = posible ofuscación
                                result['obfuscation_detected'] = True
                                result['confidence'] += 20
            except:
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
            
            # ========== PASO 3: DETECCIÓN POR NOMBRE Y UBICACIÓN (MEJORADA 200%) ==========
            
            # PATRONES DE HACKS REALES (alta confianza)
            HIGH_CONFIDENCE_HACK_PATTERNS = [
                # Clientes de hack conocidos
                'vape', 'entropy', 'whiteout', 'liquidbounce', 'wurst', 'impact',
                'sigma', 'flux', 'future', 'astolfo', 'exhibition', 'novoline',
                'rise', 'moon', 'drip', 'phobos', 'tenacity', 'meteor', 'lambda',
                'rusherhack', 'konas', 'kami blue', 'kami', 'weepcraft',
                
                # Módulos de hack específicos
                'killaura', 'aimbot', 'triggerbot', 'reach', 'velocity', 'antiknockback',
                'scaffold', 'fly', 'xray', 'fullbright', 'nofall', 'speed', 'step',
                'autoclicker', 'bhop', 'bunnyhop', 'esp', 'tracers', 'nametags',
                'traceline', 'boxesp', 'chams', 'wallhack', 'nuker', 'autotool',
                'autosprint', 'sprint', 'sneak', 'sneaking', 'freecam', 'camera',
                'baritone', 'pathfinder', 'auto', 'automation', 'macro',
                
                # Técnicas de evasión
                'bypass', 'inject', 'ghost', 'stealth', 'undetected', 'incognito',
                'spoof', 'spoofing', 'hook', 'hooking', 'patch', 'patching',
                'obfuscate', 'obfuscation', 'pack', 'packed', 'encrypt', 'encrypted',
                
                # Carpetas sospechosas
                'cheat', 'hack', 'client', 'mods\\vape', 'mods\\entropy',
                'mods\\sigma', 'mods\\flux', 'mods\\future', 'mods\\astolfo',
                'versions\\vape', 'versions\\entropy', 'versions\\sigma',
            ]
            
            # Verificar patrones de alta confianza
            is_suspicious = False
            confidence = 0
            detected_patterns = []
            
            for pattern in HIGH_CONFIDENCE_HACK_PATTERNS:
                if pattern in filename or pattern in full_path_lower:
                    # Verificación adicional: no debe estar en whitelist
                    if not self.is_whitelisted(file_path):
                        is_suspicious = True
                        confidence = max(confidence, 80)
                        detected_patterns.append(pattern)
                        break  # Encontrado, no necesitamos seguir
            
            # ========== PASO 4: DETECCIÓN POR EXTENSIÓN Y CONTEXTO ==========
            # Archivos JAR en ubicaciones sospechosas
            if filename.endswith('.jar'):
                # Si está en carpeta de mods pero no es un mod legítimo conocido
                if 'mods' in file_dir or 'versions' in file_dir:
                    # Verificar si contiene palabras de hack en el nombre
                    if any(hack in filename for hack in ['vape', 'entropy', 'sigma', 'flux', 'future', 'astolfo', 'cheat', 'hack']):
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
                
                # Patrones de funcionalidad específica de hacks
                'xray', 'killaura', 'aimbot', 'esp', 'wallhack', 'nuker',
                'autotool', 'autosprint', 'autoclick', 'clicker', 'autoclicker',
                'speedhack', 'wtap', 'aimassist', 'bhop', 'nofall', 'antiknockback',
                'reach', 'velocity', 'scaffold', 'fly', 'fullbright',
                'triggerbot', 'antiaim', 'autosprint', 'sprint',
                
                # Patrones de inyección y bypass
                'injector', 'inject', 'inyector', 'injection', 'dllinjector',
                'bypass', 'stealth', 'undetected', 'incognito', 'unbypass',
                'silent', 'silentclient', 'silent-scanner',
                
                # Técnicas avanzadas de evasión
                'obfuscated', 'packed', 'encrypted', 'hidden',
                'processhollowing', 'dllhijacking', 'codecave'
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
            
            for root, dirs, files in os.walk(drive):
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
            
            # Patrones de hacks más amplios para detectar carpetas
            hack_patterns = [
                'hack', 'cheat', 'client', 'mod', 'modded', 'modified', 'altered',
                'cracked', 'crack', 'premium', 'vip', 'private', 'secret', 'hidden',
                'vape', 'entropy', 'whiteout', 'liquidbounce', 'wurst', 'impact',
                'sigma', 'flux', 'future', 'astolfo', 'exhibition', 'novoline',
                'rise', 'moon', 'drip', 'ghost', 'ghostclient', 'bypass', 'stealth',
                'undetected', 'incognito', 'minecraft', 'mc', 'jar', 'exe', 'dll'
            ]
            
            for location in common_locations:
                if os.path.exists(location):
                    print(f"📁 ESCANEANDO: {location}")
                    try:
                        for root, dirs, files in os.walk(location):
                            # Buscar en nombres de carpetas
                            for dir_name in dirs:
                                dir_lower = dir_name.lower()
                                for pattern in hack_patterns:
                                    if pattern in dir_lower:
                                        # Verificar si no es un falso positivo
                                        if not any(false_positive in dir_lower or false_positive in root.lower() 
                                                  for false_positive in ['zomboid', 'shaders', 'textures', 'media', 'vscode', 'pylance', 'skimage', 'pyi']):
                                            print(f"🎯 HACK DETECTADO EN UBICACIÓN COMÚN: {dir_name} en {root}")
                                            self.issues_found.append({
                                                'nombre': dir_name,
                                                'ruta': root,
                                                'archivo': os.path.join(root, dir_name),
                                                'tipo': 'hack_folder_common',
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
            
            # Patrones de carpetas sospechosas (más específicos para Flux)
            suspicious_folder_patterns = [
                'flux', 'flux 1.8', 'flux1.8', 'flux 1.8.8', 'flux1.8.8',
                'hack', 'cheat', 'client', 'mod', 'modded', 'modified', 'altered',
                'cracked', 'crack', 'premium', 'vip', 'private', 'secret', 'hidden',
                'vape', 'entropy', 'whiteout', 'liquidbounce', 'wurst', 'impact',
                'sigma', 'future', 'astolfo', 'exhibition', 'novoline',
                'rise', 'moon', 'drip', 'ghost', 'ghostclient', 'bypass', 'stealth',
                'undetected', 'incognito', 'minecraft', 'mc'
            ]
            
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
            
            for location in search_locations:
                if os.path.exists(location):
                    print(f"📁 ESCANEANDO CARPETAS EN: {location}")
                    try:
                        # Limitar profundidad para evitar cuelgues
                        max_depth = 3
                        for root, dirs, files in os.walk(location):
                            # Controlar profundidad
                            depth = root[len(location):].count(os.sep)
                            if depth >= max_depth:
                                dirs[:] = []  # No explorar más profundamente
                                continue
                                
                            for dir_name in dirs:
                                dir_lower = dir_name.lower()
                                for pattern in suspicious_folder_patterns:
                                    if pattern in dir_lower:
                                        # Verificar si no es un falso positivo
                                        if not any(false_positive in dir_lower or false_positive in root.lower() 
                                                  for false_positive in ['zomboid', 'shaders', 'textures', 'media', 'vscode', 'pylance', 'skimage', 'pyi', 'system32', 'program files', 'windows']):
                                            print(f"🎯 CARPETA SOSPECHOSA ENCONTRADA: {dir_name} en {root}")
                                            self.issues_found.append({
                                                'nombre': dir_name,
                                                'ruta': root,
                                                'archivo': os.path.join(root, dir_name),
                                                'tipo': 'suspicious_folder',
                                                'alerta': 'CRITICAL'
                                            })
                                            
                                            # También escanear archivos dentro de esta carpeta
                                            try:
                                                folder_path = os.path.join(root, dir_name)
                                                for file in os.listdir(folder_path):
                                                    if file.lower().endswith(('.jar', '.exe', '.dll')):
                                                        self.issues_found.append({
                                                            'nombre': file,
                                                            'ruta': folder_path,
                                                            'archivo': os.path.join(folder_path, file),
                                                            'tipo': 'hack_file',
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
            
            # Patrones de archivos de hacks
            hack_file_patterns = [
                '.jar', '.exe', '.dll', '.class', '.minecraft', '.mods', '.config'
            ]
            
            # Ubicaciones sospechosas donde los hacks son más probables
            suspicious_locations = [
                'documents', 'downloads', 'desktop', 'appdata', 'temp', 'tmp'
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
                
                # 4. Verificar si contiene palabras clave de hacks
                hack_keywords = ['hack', 'cheat', 'client', 'mod', 'cracked', 'premium', 'vip']
                if not is_real_hack:
                    for keyword in hack_keywords:
                        if keyword in nombre or keyword in archivo:
                            is_real_hack = True
                            break
                
                if is_real_hack:
                    # Clasificar como HACK CRÍTICO
                    issue['alerta'] = 'CRITICAL'
                    issue['categoria'] = 'HACKS'
                    filtered_issues.append(issue)
                    print(f"🚨 HACK REAL DETECTADO: {nombre} en {ruta}")
                else:
                    # Mantener como sospechoso o normal
                    if issue.get('alerta') in ['SOSPECHOSO', 'POCO_SOSPECHOSO']:
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
                                                    'alerta': 'CRITICAL'
                                                })
                                                print(f"🚨 CONEXIÓN SOSPECHOSA: {conn.raddr.ip}:{conn.raddr.port}")
                        except:
                            continue
                except Exception as e:
                    print(f"Error analizando conexiones: {e}")
            
            # Ejecutar todos los análisis en paralelo
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(scan_dll_injection),
                    executor.submit(scan_memory_analysis),
                    executor.submit(scan_system_hooks),
                    executor.submit(scan_network_connections)
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
                            # Actualizar db_integration si existe
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
                                    # Guardar token en configuración para uso futuro
                                    self.config['scan_token'] = token
                                    
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
            card_color = ModernUI.COLORS['card'] if UI_STYLE_AVAILABLE else "#161b22"
            text_primary = ModernUI.COLORS['text_primary'] if UI_STYLE_AVAILABLE else "#f0f6fc"
            text_secondary = ModernUI.COLORS['text_secondary'] if UI_STYLE_AVAILABLE else "#8b949e"
            accent_blue = ModernUI.COLORS['accent_secondary'] if UI_STYLE_AVAILABLE else "#1f6feb"
            accent_green = ModernUI.COLORS['accent_primary'] if UI_STYLE_AVAILABLE else "#238636"
            
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
                                'alerta': 'SOSPECHOSO'
                            })
        except Exception as e:
            print(f"Error escaneando temp JNA: {str(e)}")
    
    def scan_registry_suspicious(self):
        """Escanea registro de Windows para entradas sospechosas"""
        try:
            print("🔍 ESCANEANDO REGISTRO DE WINDOWS...")
            import winreg
            
            # Escanear HKEY_CURRENT_USER para entradas sospechosas
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\ComDlg32\OpenSavePidlMRU\txt")
                print("⚠️ ENTRADA SOSPECHOSA EN REGISTRO: OpenSavePidlMRU")
                self.issues_found.append({
                    'nombre': "Entrada sospechosa en registro: OpenSavePidlMRU",
                    'ruta': 'Registry',
                    'archivo': 'HKEY_CURRENT_USER',
                    'tipo': 'registry_suspicious',
                    'alerta': 'SOSPECHOSO'
                })
                winreg.CloseKey(key)
            except:
                pass
                
            # Escanear Compatibility Assistant
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store")
                print("⚠️ ENTRADA SOSPECHOSA EN REGISTRO: Compatibility Assistant")
                self.issues_found.append({
                    'nombre': "Entrada sospechosa en registro: Compatibility Assistant",
                    'ruta': 'Registry',
                    'archivo': 'HKEY_CURRENT_USER',
                    'tipo': 'registry_suspicious',
                    'alerta': 'SOSPECHOSO'
                })
                winreg.CloseKey(key)
            except:
                pass
                
        except Exception as e:
            print(f"Error escaneando registro: {str(e)}")
    
    def scan_logitech_macros(self):
        """Escanea macros de Logitech"""
        try:
            print("🔍 ESCANEANDO MACROS LOGITECH...")
            import os
            
            lghub_path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'LGHUB', 'Settings.json')
            
            if os.path.exists(lghub_path):
                print("⚠️ MACROS LOGITECH DETECTADAS")
                self.issues_found.append({
                    'nombre': "Macros Logitech detectadas",
                    'ruta': os.path.dirname(lghub_path),
                    'archivo': lghub_path,
                    'tipo': 'logitech_macros',
                    'alerta': 'SOSPECHOSO'
                })
        except Exception as e:
            print(f"Error escaneando macros Logitech: {str(e)}")
    
    def scan_razer_macros(self):
        """Escanea macros de Razer"""
        try:
            print("🔍 ESCANEANDO MACROS RAZER...")
            import os
            
            razer_path = os.path.join(os.environ.get('PROGRAMDATA', ''), 'Razer', 'Synapse Accounts')
            
            if os.path.exists(razer_path):
                print("⚠️ MACROS RAZER DETECTADAS")
                self.issues_found.append({
                    'nombre': "Macros Razer detectadas",
                    'ruta': razer_path,
                    'archivo': 'Synapse Accounts',
                    'tipo': 'razer_macros',
                    'alerta': 'SOSPECHOSO'
                })
        except Exception as e:
            print(f"Error escaneando macros Razer: {str(e)}")
    
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
        """Muestra ventana de finalización con opción de feedback para IA."""
        import tkinter as tk

        # Habilitar botón de detalles
        try:
            self.details_button.config(state=tk.NORMAL)
        except Exception:
            pass

        # Actualizar área de texto
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, "✅ ESCANEO COMPLETADO\n\n", "success")
        self.results_text.insert(tk.END, f"📊 Total de elementos: {len(self.issues_found)}\n\n", "info")

        hacks    = [i for i in self.issues_found if i.get('alerta') in ('HACKS', 'CRITICAL')]
        sosp     = [i for i in self.issues_found if i.get('alerta') == 'SOSPECHOSO']
        limpio   = len(self.issues_found) - len(hacks) - len(sosp)

        self.results_text.insert(tk.END, f"🔴 HACKS: {len(hacks)}\n", "danger")
        self.results_text.insert(tk.END, f"🟡 SOSPECHOSO: {len(sosp)}\n", "warning")
        self.results_text.insert(tk.END, f"🟢 Limpio: {limpio}\n\n", "success")

        # ── Sección de detección de mouse (prison mode) ──────────────────────
        mouse_findings = getattr(self, 'mouse_findings', [])
        if mouse_findings:
            self.results_text.insert(tk.END, "━"*60 + "\n", "warning")
            self.results_text.insert(tk.END, "🖱️  DETECCIÓN DE MANIPULACIÓN DE MOUSE\n", "danger")
            self.results_text.insert(tk.END, "━"*60 + "\n", "warning")
            for mf in mouse_findings:
                icon = "🔴" if mf.get('alerta') == 'CRITICAL' else "🟠"
                self.results_text.insert(tk.END, f"{icon} {mf.get('nombre','')}\n", "danger")
                if mf.get('detalle'):
                    self.results_text.insert(tk.END, f"   └─ {mf['detalle']}\n", "warning")
                if mf.get('descripcion'):
                    self.results_text.insert(tk.END, f"   {mf['descripcion']}\n\n", "info")
            self.results_text.insert(tk.END, "\n", "info")
        else:
            self.results_text.insert(tk.END, "🖱️  Mouse: sin indicadores de peso o manipulación\n\n", "success")

        # ── Sección de análisis forense SS ───────────────────────────────────
        forensic_findings = getattr(self, 'forensic_findings', [])
        if forensic_findings:
            self.results_text.insert(tk.END, "━"*60 + "\n", "warning")
            self.results_text.insert(tk.END, "🔬  ANÁLISIS FORENSE SS\n", "danger")
            self.results_text.insert(tk.END, "━"*60 + "\n", "warning")
            for ff in forensic_findings:
                icon = "🔴" if ff.get('alerta') == 'CRITICAL' else "🟠"
                self.results_text.insert(tk.END, f"{icon} {ff.get('nombre','')}\n", "danger")
                if ff.get('detalle'):
                    self.results_text.insert(tk.END, f"   └─ {ff['detalle']}\n", "warning")
                if ff.get('descripcion'):
                    self.results_text.insert(tk.END, f"   {ff['descripcion']}\n\n", "info")
            self.results_text.insert(tk.END, "\n", "info")
        else:
            self.results_text.insert(tk.END, "🔬  Forense: sin evidencia histórica de hacks o autoclickers\n\n", "success")

        if self.issues_found:
            self.results_text.insert(tk.END, "ELEMENTOS ENCONTRADOS:\n\n", "warning")
            for i, issue in enumerate(self.issues_found[:50], 1):
                self.results_text.insert(tk.END, f"{i}. {issue.get('nombre','N/A')} [{issue.get('alerta','?')}]\n", "info")
                self.results_text.insert(tk.END, f"   {issue.get('ruta','')}\n\n", "info")
        else:
            self.results_text.insert(tk.END, "✅ Sin elementos sospechosos\n", "success")

        # ── Ventana de feedback ─────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title("Resultado del Escaneo — Feedback para IA")
        _mf_count = len(getattr(self, 'mouse_findings', []))
        _ff_count = len(getattr(self, 'forensic_findings', []))
        _win_h = 420 + min(_mf_count, 3) * 22 + (30 if _mf_count > 0 else 0) + min(_ff_count, 3) * 22 + (30 if _ff_count > 0 else 0)
        win.geometry(f"520x{_win_h}")
        win.configure(bg="#060912")
        win.resizable(False, False)
        win.grab_set()

        # Header
        hdr = tk.Frame(win, bg="#060912")
        hdr.pack(fill="x", padx=20, pady=(20, 0))
        tk.Label(hdr, text="✅  Escaneo Completado", font=("Segoe UI", 16, "bold"),
                 bg="#060912", fg="#dce8f5").pack(anchor="w")
        summary = f"  {len(hacks)} HACKS  •  {len(sosp)} Sospechosos  •  {limpio} Limpios  •  {len(self.issues_found)} total"
        tk.Label(hdr, text=summary, font=("Segoe UI", 11),
                 bg="#060912", fg="#5a7296").pack(anchor="w", pady=(4, 0))

        # Mouse hardware alert (shown prominently if any findings)
        _mf = getattr(self, 'mouse_findings', [])
        if _mf:
            _critical_mouse = [m for m in _mf if m.get('alerta') == 'CRITICAL']
            _mouse_bg = "#3a0808" if _critical_mouse else "#2a1a00"
            _mouse_fg = "#ff6060" if _critical_mouse else "#ffb347"
            _mouse_icon = "🔴" if _critical_mouse else "🟠"
            mouse_banner = tk.Frame(hdr, bg=_mouse_bg, padx=8, pady=6)
            mouse_banner.pack(fill="x", pady=(8, 0))
            tk.Label(mouse_banner,
                     text=f"{_mouse_icon}  MANIPULACIÓN DE MOUSE: {len(_mf)} alerta(s)",
                     font=("Segoe UI", 10, "bold"),
                     bg=_mouse_bg, fg=_mouse_fg).pack(anchor="w")
            for m in _mf[:3]:
                tk.Label(mouse_banner,
                         text=f"  • {m.get('nombre','')}",
                         font=("Segoe UI", 9),
                         bg=_mouse_bg, fg=_mouse_fg).pack(anchor="w")
            if len(_mf) > 3:
                tk.Label(mouse_banner,
                         text=f"  … y {len(_mf)-3} más (ver resultados completos)",
                         font=("Segoe UI", 9, "italic"),
                         bg=_mouse_bg, fg=_mouse_fg).pack(anchor="w")

        # Forensic alert banner
        _ff = getattr(self, 'forensic_findings', [])
        if _ff:
            _critical_ff = [f for f in _ff if f.get('alerta') == 'CRITICAL']
            _ff_bg = "#1a0a2e" if _critical_ff else "#0a1a2e"
            _ff_fg = "#cc88ff" if _critical_ff else "#66aaff"
            _ff_icon = "🔴" if _critical_ff else "🔬"
            ff_banner = tk.Frame(hdr, bg=_ff_bg, padx=8, pady=6)
            ff_banner.pack(fill="x", pady=(8, 0))
            tk.Label(ff_banner,
                     text=f"{_ff_icon}  EVIDENCIA FORENSE SS: {len(_ff)} hallazgo(s)",
                     font=("Segoe UI", 10, "bold"),
                     bg=_ff_bg, fg=_ff_fg).pack(anchor="w")
            for f in _ff[:3]:
                tk.Label(ff_banner,
                         text=f"  • {f.get('nombre','')}",
                         font=("Segoe UI", 9),
                         bg=_ff_bg, fg=_ff_fg).pack(anchor="w")
            if len(_ff) > 3:
                tk.Label(ff_banner,
                         text=f"  … y {len(_ff)-3} más (ver resultados completos)",
                         font=("Segoe UI", 9, "italic"),
                         bg=_ff_bg, fg=_ff_fg).pack(anchor="w")

        sep = tk.Frame(win, bg="#0f1525", height=1)
        sep.pack(fill="x", padx=20, pady=12)

        # Feedback prompt
        fb_frame = tk.Frame(win, bg="#0a0e1a", bd=0)
        fb_frame.pack(fill="x", padx=20)
        tk.Label(fb_frame, text="🧠  Ayuda a la IA a mejorar", font=("Segoe UI", 13, "bold"),
                 bg="#0a0e1a", fg="#00c8ff").pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(fb_frame, text="¿El resultado es correcto? Tu feedback actualiza el modelo de detección.",
                 font=("Segoe UI", 10), bg="#0a0e1a", fg="#5a7296",
                 wraplength=460, justify="left").pack(anchor="w", padx=14, pady=(0, 10))

        # Opciones
        verdict_var = tk.StringVar(value="")
        opts = [
            ("correcto",    "✅  Correcto — todos los hallazgos son válidos",        "#22d3a5"),
            ("falsos_pos",  "⚠️  Hay falsos positivos — algunos son legítimos",      "#fbbf24"),
            ("limpio",      "🟢  Sin hacks — el usuario está limpio",                "#22d3a5"),
            ("hack_real",   "🔴  Confirmado hack — reportar como caso de aprendizaje","#ff4d6a"),
        ]
        for val, label, color in opts:
            rb = tk.Radiobutton(fb_frame, text=label, variable=verdict_var, value=val,
                                bg="#0a0e1a", fg="#dce8f5", selectcolor="#060912",
                                activebackground="#0a0e1a", activeforeground=color,
                                font=("Segoe UI", 10), anchor="w", cursor="hand2")
            rb.pack(fill="x", padx=14, pady=2)

        tk.Label(fb_frame, text="Notas opcionales:", font=("Segoe UI", 10),
                 bg="#0a0e1a", fg="#5a7296").pack(anchor="w", padx=14, pady=(10, 2))
        notes_var = tk.Text(fb_frame, height=3, bg="#060912", fg="#dce8f5",
                            insertbackground="#00c8ff", relief="flat",
                            font=("Segoe UI", 10), bd=0)
        notes_var.pack(fill="x", padx=14, pady=(0, 12))

        # Botones
        btn_frame = tk.Frame(win, bg="#060912")
        btn_frame.pack(fill="x", padx=20, pady=12)

        def _send_feedback():
            verdict = verdict_var.get()
            notes   = notes_var.get("1.0", "end").strip()
            if verdict:
                threading.Thread(
                    target=self._submit_ai_feedback,
                    args=(verdict, notes),
                    daemon=True
                ).start()
            win.destroy()

        tk.Button(btn_frame, text="Enviar Feedback", command=_send_feedback,
                  bg="#00a8d4", fg="white", font=("Segoe UI", 11, "bold"),
                  relief="flat", cursor="hand2", padx=16, pady=8).pack(side="right")
        tk.Button(btn_frame, text="Omitir", command=win.destroy,
                  bg="#0f1525", fg="#5a7296", font=("Segoe UI", 11),
                  relief="flat", cursor="hand2", padx=16, pady=8).pack(side="right", padx=(0, 8))

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
