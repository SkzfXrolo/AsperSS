"""
Sistema de Patrones Legítimos - Aprende qué archivos son normales
Reduce falsos positivos aprendiendo de feedback del staff
"""
import json
import sqlite3
import os
import hashlib
from typing import Dict, List, Set, Tuple
from pathlib import Path

class LegitimatePatterns:
    """Sistema que aprende patrones de archivos legítimos para reducir falsos positivos"""
    
    def __init__(self, database_path='scanner_db.sqlite'):
        self.database_path = database_path
        self.legitimate_patterns = {
            'file_names': set(),
            'file_paths': set(),
            'file_extensions': set(),
            'folder_names': set(),
            'process_names': set(),
            'file_hashes': set(),
            'context_patterns': {}  # Patrones contextuales: {pattern: {count, confidence}}
        }
        
        # Cargar patrones aprendidos de la base de datos
        self.load_learned_patterns()
    
    def load_learned_patterns(self):
        """Carga patrones legítimos aprendidos de la base de datos"""
        try:
            if not os.path.exists(self.database_path):
                return
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Cargar hashes legítimos
            cursor.execute('''
                SELECT file_hash FROM learned_hashes 
                WHERE is_hack = 0 AND is_active = 1
            ''')
            self.legitimate_patterns['file_hashes'] = {row[0] for row in cursor.fetchall()}
            
            # Cargar patrones legítimos de feedback
            cursor.execute('''
                SELECT DISTINCT 
                    sr.file_path, sr.file_name, sr.file_hash,
                    COUNT(*) as feedback_count
                FROM scan_results sr
                JOIN staff_feedback sf ON sr.id = sf.result_id
                WHERE sf.staff_verification = 'legitimate'
                GROUP BY sr.file_path, sr.file_name, sr.file_hash
                HAVING COUNT(*) >= 2
            ''')
            
            for row in cursor.fetchall():
                file_path, file_name, file_hash, count = row
                
                if file_name:
                    self.legitimate_patterns['file_names'].add(file_name.lower())
                if file_path:
                    # Extraer patrones de ruta
                    path_parts = file_path.lower().split(os.sep)
                    for part in path_parts:
                        if len(part) > 3:  # Ignorar partes muy cortas
                            self.legitimate_patterns['folder_names'].add(part)
                
                if file_hash:
                    self.legitimate_patterns['file_hashes'].add(file_hash)
            
            # Cargar extensiones legítimas comunes
            cursor.execute('''
                SELECT DISTINCT 
                    SUBSTR(sr.file_name, LENGTH(sr.file_name) - INSTR(REVERSE(sr.file_name), '.') + 1) as ext
                FROM scan_results sr
                JOIN staff_feedback sf ON sr.id = sf.result_id
                WHERE sf.staff_verification = 'legitimate'
                AND sr.file_name LIKE '%.%'
                GROUP BY ext
                HAVING COUNT(*) >= 3
            ''')
            
            for row in cursor.fetchall():
                ext = row[0].lower()
                if ext and len(ext) <= 10:  # Extensiones razonables
                    self.legitimate_patterns['file_extensions'].add(ext)
            
            conn.close()
            
            print(f"✅ Patrones legítimos cargados:")
            print(f"   - {len(self.legitimate_patterns['file_names'])} nombres de archivo")
            print(f"   - {len(self.legitimate_patterns['folder_names'])} nombres de carpeta")
            print(f"   - {len(self.legitimate_patterns['file_hashes'])} hashes")
            print(f"   - {len(self.legitimate_patterns['file_extensions'])} extensiones")
            
        except Exception as e:
            print(f"⚠️ Error cargando patrones legítimos: {e}")
    
    def is_legitimate(self, file_path: str, file_name: str = None, file_hash: str = None, 
                     context: Dict = None) -> Tuple[bool, float]:
        """
        Verifica si un archivo es legítimo basado en patrones aprendidos
        
        Returns:
            Tuple[bool, float]: (es_legitimo, confianza)
        """
        if not file_path:
            return False, 0.0
        
        file_path_lower = file_path.lower()
        file_name_lower = (file_name or os.path.basename(file_path)).lower()
        
        confidence = 0.0
        matches = []
        
        # 1. Verificar hash conocido como legítimo (máxima confianza)
        if file_hash and file_hash in self.legitimate_patterns['file_hashes']:
            return True, 1.0
        
        # 2. Verificar nombre de archivo conocido
        if file_name_lower in self.legitimate_patterns['file_names']:
            confidence += 0.4
            matches.append('nombre_conocido')
        
        # 3. Verificar patrones de carpeta
        path_parts = file_path_lower.split(os.sep)
        for part in path_parts:
            if part in self.legitimate_patterns['folder_names']:
                confidence += 0.2
                matches.append(f'carpeta_conocida: {part}')
                break  # Solo contar una vez
        
        # 4. Verificar extensión conocida como legítima
        if file_name_lower:
            for ext in self.legitimate_patterns['file_extensions']:
                if file_name_lower.endswith(ext):
                    confidence += 0.2
                    matches.append(f'extension_conocida: {ext}')
                    break
        
        # 5. Verificar contexto (si se proporciona)
        if context:
            context_confidence = self._check_context(context)
            confidence += context_confidence * 0.2
        
        # Normalizar confianza (0-1)
        confidence = min(1.0, confidence)
        
        # Si la confianza es alta, es legítimo
        is_legitimate = confidence >= 0.5
        
        return is_legitimate, confidence
    
    def _check_context(self, context: Dict) -> float:
        """Verifica el contexto del archivo"""
        context_score = 0.0
        
        # Ubicaciones legítimas conocidas
        legitimate_locations = [
            'program files', 'program files (x86)', 'windows\\system32',
            'appdata\\roaming\\minecraft', 'appdata\\local\\programs',
            'steam', 'epic games', 'origin', 'uplay'
        ]
        
        file_path = context.get('file_path', '').lower()
        for location in legitimate_locations:
            if location in file_path:
                context_score += 0.3
                break
        
        # Procesos legítimos relacionados
        related_processes = context.get('related_processes', [])
        for proc in related_processes:
            proc_lower = proc.lower()
            if any(legit in proc_lower for legit in ['minecraft', 'java', 'steam', 'epic']):
                context_score += 0.2
                break
        
        return min(1.0, context_score)
    
    def learn_from_feedback(self, file_path: str, file_name: str, file_hash: str, 
                           is_legitimate: bool, feedback_count: int = 1):
        """Aprende de feedback del staff"""
        try:
            if not os.path.exists(self.database_path):
                return
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            if is_legitimate:
                # Aprender como legítimo
                file_name_lower = file_name.lower() if file_name else ''
                file_path_lower = file_path.lower()
                
                # Agregar a patrones aprendidos
                if file_name_lower:
                    self.legitimate_patterns['file_names'].add(file_name_lower)
                
                # Extraer partes de la ruta
                path_parts = file_path_lower.split(os.sep)
                for part in path_parts:
                    if len(part) > 3:
                        self.legitimate_patterns['folder_names'].add(part)
                
                # Agregar hash si existe
                if file_hash:
                    self.legitimate_patterns['file_hashes'].add(file_hash)
                
                # Guardar en base de datos
                if file_hash:
                    cursor.execute('''
                        INSERT OR REPLACE INTO learned_hashes 
                        (file_hash, is_hack, is_active, learned_from)
                        VALUES (?, 0, 1, 'staff_feedback')
                    ''', (file_hash,))
                
                conn.commit()
                print(f"✅ Aprendido como legítimo: {file_name}")
            
            conn.close()
            
        except Exception as e:
            print(f"⚠️ Error aprendiendo de feedback: {e}")
    
    def get_legitimate_patterns_summary(self) -> Dict:
        """Obtiene un resumen de los patrones legítimos aprendidos"""
        return {
            'file_names_count': len(self.legitimate_patterns['file_names']),
            'folder_names_count': len(self.legitimate_patterns['folder_names']),
            'file_hashes_count': len(self.legitimate_patterns['file_hashes']),
            'file_extensions_count': len(self.legitimate_patterns['file_extensions']),
            'total_patterns': (
                len(self.legitimate_patterns['file_names']) +
                len(self.legitimate_patterns['folder_names']) +
                len(self.legitimate_patterns['file_hashes']) +
                len(self.legitimate_patterns['file_extensions'])
            )
        }


