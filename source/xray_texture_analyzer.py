"""
Análisis de Texturas X-ray y Resource Packs Modificados
Detecta texturas modificadas que permiten ver a través de bloques
"""
import os
from PIL import Image
import json
from typing import List, Dict, Tuple

class XRayTextureAnalyzer:
    """Analizador de texturas X-ray"""
    
    # Texturas críticas que comúnmente se modifican para X-ray
    CRITICAL_TEXTURES = [
        'stone', 'dirt', 'grass', 'cobblestone', 'gravel',
        'coal_ore', 'iron_ore', 'gold_ore', 'diamond_ore',
        'emerald_ore', 'lapis_ore', 'redstone_ore',
        'netherrack', 'end_stone'
    ]
    
    def __init__(self):
        self.minecraft_paths = []
        self._find_minecraft_paths()
    
    def _find_minecraft_paths(self):
        """Encuentra las rutas de instalación de Minecraft"""
        user_home = os.path.expanduser("~")
        possible_paths = [
            os.path.join(user_home, "AppData", "Roaming", ".minecraft"),
            os.path.join(user_home, ".minecraft"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                self.minecraft_paths.append(path)
    
    def scan_resource_packs(self) -> List[Dict]:
        """Escanea resource packs buscando texturas X-ray"""
        detected = []
        
        for minecraft_path in self.minecraft_paths:
            resourcepacks_path = os.path.join(minecraft_path, "resourcepacks")
            textures_path = os.path.join(minecraft_path, "textures")
            
            # Escanear resource packs
            if os.path.exists(resourcepacks_path):
                detected.extend(self._scan_directory(resourcepacks_path, "resourcepack"))
            
            # Escanear texturas directas
            if os.path.exists(textures_path):
                detected.extend(self._scan_directory(textures_path, "texture"))
        
        return detected
    
    def _scan_directory(self, directory: str, source_type: str) -> List[Dict]:
        """Escanea un directorio buscando texturas modificadas"""
        detected = []
        
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith('.png'):
                        file_path = os.path.join(root, file)
                        result = self._analyze_texture(file_path, source_type)
                        if result:
                            detected.append(result)
        except Exception as e:
            print(f"⚠️ Error escaneando directorio {directory}: {e}")
        
        return detected
    
    def _analyze_texture(self, file_path: str, source_type: str) -> Dict:
        """Analiza una textura individual buscando modificaciones X-ray"""
        try:
            # Verificar si es una textura crítica
            file_name = os.path.basename(file_path).lower()
            is_critical = any(texture in file_name for texture in self.CRITICAL_TEXTURES)
            
            if not is_critical:
                return None
            
            # Abrir imagen
            img = Image.open(file_path)
            
            # Convertir a RGBA si no lo es
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Analizar transparencia
            alpha_channel = img.split()[3]  # Canal alpha
            alpha_data = list(alpha_channel.getdata())
            
            # Contar píxeles transparentes
            transparent_pixels = sum(1 for alpha in alpha_data if alpha < 128)
            total_pixels = len(alpha_data)
            transparency_ratio = transparent_pixels / total_pixels if total_pixels > 0 else 0
            
            # XRay real: texturas de bloques sólidos con >40% píxeles transparentes
            if transparency_ratio > 0.40:
                return {
                    'type': 'xray_texture',
                    'name': os.path.basename(file_path),
                    'path': file_path,
                    'source_type': source_type,
                    'transparency_ratio': transparency_ratio,
                    'transparent_pixels': transparent_pixels,
                    'total_pixels': total_pixels,
                    'confidence': min(0.9, transparency_ratio * 5),  # Más transparencia = más confianza
                    'alert': 'SOSPECHOSO' if transparency_ratio < 0.5 else 'CRITICAL'
                }
            
            # Colores saturados/brillantes NO son indicador de XRay — son packs PvP normales.
        
        except Exception as e:
            # Error al analizar, no reportar
            pass
        
        return None
    
    def check_mcmeta_files(self) -> List[Dict]:
        """Verifica archivos .mcmeta que podrían modificar texturas"""
        detected = []
        
        for minecraft_path in self.minecraft_paths:
            resourcepacks_path = os.path.join(minecraft_path, "resourcepacks")
            
            if not os.path.exists(resourcepacks_path):
                continue
            
            try:
                for root, dirs, files in os.walk(resourcepacks_path):
                    for file in files:
                        if file.endswith('.mcmeta'):
                            file_path = os.path.join(root, file)
                            result = self._analyze_mcmeta(file_path)
                            if result:
                                detected.append(result)
            except Exception as e:
                print(f"⚠️ Error verificando archivos .mcmeta: {e}")
        
        return detected
    
    def analyze_pack(self, pack_path: str) -> Dict:
        """Analiza un resource pack específico (carpeta o .zip) buscando X-Ray."""
        try:
            import zipfile
            textures_to_check = []

            if os.path.isdir(pack_path):
                for root, _, files in os.walk(pack_path):
                    for fname in files:
                        if fname.lower().endswith('.png') and any(t in fname.lower() for t in self.CRITICAL_TEXTURES):
                            textures_to_check.append(os.path.join(root, fname))
            elif pack_path.lower().endswith('.zip') and os.path.isfile(pack_path):
                import tempfile, shutil
                tmp_dir = tempfile.mkdtemp()
                try:
                    with zipfile.ZipFile(pack_path, 'r') as zf:
                        zf.extractall(tmp_dir)
                    for root, _, files in os.walk(tmp_dir):
                        for fname in files:
                            if fname.lower().endswith('.png') and any(t in fname.lower() for t in self.CRITICAL_TEXTURES):
                                textures_to_check.append(os.path.join(root, fname))
                finally:
                    shutil.rmtree(tmp_dir, ignore_errors=True)

            xray_found = False
            patterns = []
            max_conf = 0.0
            for tex_path in textures_to_check[:50]:
                result = self._analyze_texture(tex_path, 'resourcepack')
                if result:
                    xray_found = True
                    patterns.append(result.get('name', ''))
                    max_conf = max(max_conf, result.get('confidence', 0))

            return {'is_xray': xray_found, 'confidence': max_conf, 'patterns': patterns}
        except Exception:
            return {'is_xray': False, 'confidence': 0.0, 'patterns': []}

    def _analyze_mcmeta(self, file_path: str) -> Dict:
        """Analiza un archivo .mcmeta buscando modificaciones sospechosas"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                data = json.loads(content)
            
            # Buscar configuraciones que modifiquen transparencia o visibilidad
            if 'texture' in data:
                texture_data = data['texture']
                if isinstance(texture_data, dict):
                    # Verificar si tiene configuraciones de transparencia
                    if 'blur' in texture_data or 'clamp' in texture_data:
                        # Esto es normal, pero si está en texturas críticas podría ser sospechoso
                        file_name = os.path.basename(file_path).lower()
                        if any(texture in file_name for texture in self.CRITICAL_TEXTURES):
                            return {
                                'type': 'modified_mcmeta',
                                'name': os.path.basename(file_path),
                                'path': file_path,
                                'confidence': 0.4,
                                'alert': 'POCO_SOSPECHOSO'
                            }
        
        except Exception:
            pass
        
        return None


