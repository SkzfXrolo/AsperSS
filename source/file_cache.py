"""
Sistema de Caché Inteligente para Archivos Escaneados
Optimiza escaneos subsecuentes guardando hash y resultados de archivos ya escaneados
"""
import sqlite3
import hashlib
import os
from datetime import datetime

class FileCache:
    """Sistema de caché para archivos escaneados"""
    
    def __init__(self, database_path='scanner_db.sqlite'):
        self.database_path = database_path
        self._init_cache_table()
    
    def _init_cache_table(self):
        """Inicializa la tabla de caché en la base de datos"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS file_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_size INTEGER,
                    file_modified REAL,
                    scan_result TEXT,
                    is_suspicious BOOLEAN,
                    confidence REAL,
                    detected_patterns TEXT,
                    last_scanned TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    scan_count INTEGER DEFAULT 1,
                    UNIQUE(file_path, file_hash)
                )
            ''')
            
            # Índices para búsqueda rápida
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON file_cache(file_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_path ON file_cache(file_path)')
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Error inicializando caché: {e}")
    
    def calculate_file_hash(self, file_path):
        """Calcula el hash SHA256 de un archivo"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            return None
    
    def get_file_info(self, file_path):
        """Obtiene información de un archivo (tamaño, fecha de modificación)"""
        try:
            stat = os.stat(file_path)
            return {
                'size': stat.st_size,
                'modified': stat.st_mtime
            }
        except Exception:
            return None
    
    def is_cached(self, file_path):
        """Verifica si un archivo está en caché y si necesita re-escaneo"""
        try:
            file_info = self.get_file_info(file_path)
            if not file_info:
                return None
            
            file_hash = self.calculate_file_hash(file_path)
            if not file_hash:
                return None
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT scan_result, is_suspicious, confidence, detected_patterns,
                       file_size, file_modified, last_scanned
                FROM file_cache
                WHERE file_path = ? AND file_hash = ? AND file_size = ? AND file_modified = ?
            ''', (file_path, file_hash, file_info['size'], file_info['modified']))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # Archivo en caché y no modificado
                return {
                    'cached': True,
                    'scan_result': result[0],
                    'is_suspicious': bool(result[1]),
                    'confidence': result[2],
                    'detected_patterns': result[3],
                    'last_scanned': result[6]
                }
            else:
                # Archivo no en caché o modificado
                return {'cached': False}
        except Exception as e:
            return None
    
    def cache_result(self, file_path, is_suspicious=False, confidence=0, 
                    detected_patterns=None, scan_result=None):
        """Guarda el resultado de un escaneo en caché"""
        try:
            file_info = self.get_file_info(file_path)
            if not file_info:
                return False
            
            file_hash = self.calculate_file_hash(file_path)
            if not file_hash:
                return False
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Convertir detected_patterns a JSON si es una lista
            if detected_patterns and isinstance(detected_patterns, list):
                import json
                detected_patterns = json.dumps(detected_patterns)
            
            if scan_result and isinstance(scan_result, dict):
                import json
                scan_result = json.dumps(scan_result)
            
            cursor.execute('''
                INSERT OR REPLACE INTO file_cache 
                (file_path, file_hash, file_size, file_modified, scan_result,
                 is_suspicious, confidence, detected_patterns, last_scanned, scan_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                        COALESCE((SELECT scan_count FROM file_cache WHERE file_path = ? AND file_hash = ?), 0) + 1)
            ''', (file_path, file_hash, file_info['size'], file_info['modified'],
                  scan_result, is_suspicious, confidence, detected_patterns,
                  file_path, file_hash))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"⚠️ Error guardando en caché: {e}")
            return False
    
    def get_cache_stats(self):
        """Obtiene estadísticas del caché"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM file_cache')
            total_cached = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM file_cache WHERE is_suspicious = 1')
            suspicious_cached = cursor.fetchone()[0]
            
            cursor.execute('SELECT SUM(scan_count) FROM file_cache')
            total_scans = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                'total_cached': total_cached,
                'suspicious_cached': suspicious_cached,
                'total_scans_saved': total_scans - total_cached  # Escaneos evitados
            }
        except Exception as e:
            return {'error': str(e)}
    
    def clear_old_cache(self, days=30):
        """Limpia entradas de caché más antiguas que X días"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM file_cache
                WHERE last_scanned < datetime('now', '-' || ? || ' days')
            ''', (days,))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            return deleted
        except Exception as e:
            print(f"⚠️ Error limpiando caché: {e}")
            return 0


