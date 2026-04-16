"""
Analizador de IA para resultados de escaneo
Utiliza análisis heurístico y machine learning para mejorar la detección
SISTEMA DE APRENDIZAJE PROGRESIVO: Carga patrones aprendidos de la base de datos
"""
import json
import re
import os
import sqlite3
from typing import Dict, List, Tuple

class AIAnalyzer:
    """Analizador de IA para resultados de escaneo con aprendizaje progresivo"""
    
    def __init__(self, database_path='scanner_db.sqlite', api_url=None, scan_token=None):
        self.database_path = database_path
        self.api_url = api_url
        self.scan_token = scan_token
        
        # Patrones base (iniciales)
        self.suspicious_patterns = {
            'high_risk': [
                'inject', 'bypass', 'stealth', 'undetected', 'incognito',
                'killaura', 'aimbot', 'triggerbot', 'reach', 'velocity',
                'scaffold', 'fly', 'xray', 'fullbright'
            ],
            'medium_risk': [
                'ghost', 'client', 'mod', 'hack', 'cheat',
                'sigma', 'flux', 'future', 'astolfo'
            ],
            'low_risk': [
                'mod', 'client', 'jar', 'minecraft'
            ]
        }
        
        # Cargar patrones aprendidos (primero de BD local, luego de API si está disponible)
        self.load_learned_patterns()
        
        # Intentar cargar desde API si está configurada
        if self.api_url:
            self.load_patterns_from_api()
        
        # Patrones de ofuscación
        self.obfuscation_indicators = [
            'high_non_ascii_ratio',
            'unusual_entropy',
            'packed_executable',
            'encrypted_strings'
        ]
        
        # Hashes aprendidos (se cargan dinámicamente)
        self.learned_hashes = set()
        self.load_learned_hashes()
        
        # Intentar cargar hashes desde API si está configurada
        if self.api_url:
            self.load_hashes_from_api()
    
    def load_learned_patterns(self):
        """Carga patrones aprendidos de la base de datos"""
        try:
            if not os.path.exists(self.database_path):
                return
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT pattern_value, pattern_category
                FROM learned_patterns
                WHERE is_active = 1
            ''')
            
            for pattern, category in cursor.fetchall():
                if category in self.suspicious_patterns:
                    if pattern not in self.suspicious_patterns[category]:
                        self.suspicious_patterns[category].append(pattern)
                        print(f"✅ Patrón aprendido cargado: {pattern} ({category})")
            
            conn.close()
        except Exception as e:
            print(f"⚠️ Error cargando patrones aprendidos: {e}")
    
    def load_learned_hashes(self):
        """Carga hashes aprendidos de la base de datos"""
        try:
            if not os.path.exists(self.database_path):
                return
            
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT file_hash FROM learned_hashes WHERE is_hack = 1
            ''')
            
            self.learned_hashes = {row[0] for row in cursor.fetchall()}
            if self.learned_hashes:
                print(f"✅ {len(self.learned_hashes)} hashes aprendidos cargados")
            
            conn.close()
        except Exception as e:
            print(f"⚠️ Error cargando hashes aprendidos: {e}")
    
    def load_patterns_from_api(self):
        """Carga patrones aprendidos desde la API (actualización dinámica)"""
        try:
            import requests
            
            if not self.api_url:
                return
            
            response = requests.get(
                f"{self.api_url}/api/ai-model/latest",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                patterns = data.get('patterns', {})
                
                # Agregar patrones desde API
                for category in ['high_risk', 'medium_risk', 'low_risk']:
                    if category in patterns:
                        for pattern_data in patterns[category]:
                            pattern_value = pattern_data.get('value', '')
                            if pattern_value and pattern_value not in self.suspicious_patterns[category]:
                                self.suspicious_patterns[category].append(pattern_value)
                
                print(f"✅ {data.get('patterns_count', 0)} patrones cargados desde API")
                
                # Guardar en archivo local para uso offline
                self.save_model_to_file(data)
                
        except Exception as e:
            print(f"⚠️ Error cargando patrones desde API: {e}")
    
    def load_hashes_from_api(self):
        """Carga hashes aprendidos desde la API (actualización dinámica)"""
        try:
            import requests
            
            if not self.api_url:
                return
            
            response = requests.get(
                f"{self.api_url}/api/ai-model/latest",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                hashes = data.get('hashes', [])
                
                # Agregar hashes desde API
                for hash_data in hashes:
                    if hash_data.get('is_hack'):
                        self.learned_hashes.add(hash_data.get('hash'))
                
                print(f"✅ {len(hashes)} hashes cargados desde API")
                
        except Exception as e:
            print(f"⚠️ Error cargando hashes desde API: {e}")
    
    def save_model_to_file(self, model_data):
        """Guarda el modelo en un archivo JSON local para uso offline"""
        try:
            import json
            import os
            
            models_dir = 'models'
            os.makedirs(models_dir, exist_ok=True)
            
            model_file = os.path.join(models_dir, 'ai_model_latest.json')
            with open(model_file, 'w', encoding='utf-8') as f:
                json.dump(model_data, f, indent=2)
            
        except Exception as e:
            print(f"⚠️ Error guardando modelo local: {e}")
    
    def load_model_from_file(self):
        """Carga el modelo desde archivo local (si no hay conexión a API)"""
        try:
            import json
            import os
            
            model_file = os.path.join('models', 'ai_model_latest.json')
            if os.path.exists(model_file):
                with open(model_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                patterns = data.get('patterns', {})
                for category in ['high_risk', 'medium_risk', 'low_risk']:
                    if category in patterns:
                        for pattern_data in patterns[category]:
                            pattern_value = pattern_data.get('value', '')
                            if pattern_value and pattern_value not in self.suspicious_patterns[category]:
                                self.suspicious_patterns[category].append(pattern_value)
                
                hashes = data.get('hashes', [])
                for hash_data in hashes:
                    if hash_data.get('is_hack'):
                        self.learned_hashes.add(hash_data.get('hash'))
                
                print(f"✅ Modelo cargado desde archivo local")
                
        except Exception as e:
            print(f"⚠️ Error cargando modelo local: {e}")
    
    def reload_learned_data(self):
        """Recarga patrones y hashes aprendidos (útil después de actualizaciones)"""
        self.load_learned_patterns()
        self.load_learned_hashes()
        
        # Intentar actualizar desde API
        if self.api_url:
            self.load_patterns_from_api()
            self.load_hashes_from_api()
        else:
            # Si no hay API, cargar desde archivo local
            self.load_model_from_file()
    
    def analyze_issue(self, issue: Dict) -> Dict:
        """
        Analiza un issue individual y proporciona análisis de IA
        
        Returns:
            Dict con 'analysis', 'confidence', 'risk_level', 'recommendations'
        """
        analysis = {
            'analysis': '',
            'confidence': 0.0,
            'risk_level': 'unknown',
            'recommendations': []
        }
        
        # Extraer información del issue
        issue_name = issue.get('nombre', '').lower()
        issue_path = issue.get('ruta', '').lower()
        issue_type = issue.get('tipo', '').lower()
        alert_level = issue.get('alerta', '').lower()
        confidence = issue.get('confidence', 0)
        detected_patterns = issue.get('detected_patterns', [])
        obfuscation = issue.get('obfuscation_detected', False)
        
        # Análisis heurístico
        risk_score = 0.0
        risk_factors = []
        
        # 0. Verificar hash aprendido (prioridad máxima)
        file_hash = issue.get('file_hash', '')
        if file_hash and file_hash in self.learned_hashes:
            risk_score = 1.0  # 100% de confianza si el hash está en la BD
            risk_factors.append("Hash confirmado como hack en base de datos aprendida")
            analysis['analysis'] = "⚠️ HACK CONFIRMADO: Este archivo fue marcado como hack por el staff y está en la base de datos aprendida."
            analysis['confidence'] = 1.0
            analysis['risk_level'] = 'critical'
            analysis['recommendations'] = [
                "⚠️ ACCIÓN INMEDIATA: Este archivo fue confirmado como hack por el staff",
                "Se recomienda eliminación inmediata"
            ]
            return analysis
        
        # 1. Verificar patrones de alto riesgo (incluyendo aprendidos)
        for pattern in self.suspicious_patterns['high_risk']:
            if pattern in issue_name or pattern in issue_path:
                risk_score += 0.4
                risk_factors.append(f"Patrón de alto riesgo detectado: {pattern}")
        
        # 2. Verificar patrones de riesgo medio
        for pattern in self.suspicious_patterns['medium_risk']:
            if pattern in issue_name or pattern in issue_path:
                risk_score += 0.2
                risk_factors.append(f"Patrón de riesgo medio detectado: {pattern}")
        
        # 3. Verificar ofuscación
        if obfuscation:
            risk_score += 0.3
            risk_factors.append("Ofuscación detectada - aumenta probabilidad de hack")
        
        # 4. Verificar confianza del scanner
        if confidence >= 80:
            risk_score += 0.2
        elif confidence >= 60:
            risk_score += 0.1
        
        # 5. Verificar múltiples patrones detectados
        if len(detected_patterns) >= 3:
            risk_score += 0.2
            risk_factors.append(f"Múltiples patrones detectados ({len(detected_patterns)})")
        
        # 6. Verificar ubicación sospechosa
        suspicious_locations = ['temp', 'downloads', 'desktop', 'appdata']
        if any(loc in issue_path for loc in suspicious_locations):
            risk_score += 0.1
            risk_factors.append("Ubicación sospechosa")
        
        # Normalizar score (0-1)
        risk_score = min(1.0, risk_score)
        
        # Determinar nivel de riesgo
        if risk_score >= 0.7:
            risk_level = 'critical'
        elif risk_score >= 0.5:
            risk_level = 'high'
        elif risk_score >= 0.3:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        # Generar análisis
        analysis_text = f"Análisis de IA: "
        if risk_factors:
            analysis_text += "Se detectaron los siguientes factores de riesgo: " + ", ".join(risk_factors[:3])
        else:
            analysis_text += "No se detectaron factores de riesgo significativos."
        
        # Generar recomendaciones
        recommendations = []
        if risk_score >= 0.7:
            recommendations.append("⚠️ ACCIÓN INMEDIATA REQUERIDA: Este archivo presenta un riesgo crítico")
            recommendations.append("Se recomienda eliminar o aislar este archivo inmediatamente")
        elif risk_score >= 0.5:
            recommendations.append("⚠️ Se recomienda revisar este archivo en detalle")
            recommendations.append("Considerar eliminación si no es necesario")
        elif risk_score >= 0.3:
            recommendations.append("ℹ️ Archivo sospechoso - revisar manualmente")
        else:
            recommendations.append("ℹ️ Probable falso positivo - verificar manualmente")
        
        analysis['analysis'] = analysis_text
        analysis['confidence'] = risk_score
        analysis['risk_level'] = risk_level
        analysis['recommendations'] = recommendations
        analysis['risk_factors'] = risk_factors
        
        return analysis
    
    def analyze_batch(self, issues: List[Dict]) -> List[Dict]:
        """Analiza un lote de issues"""
        analyzed_issues = []
        
        for issue in issues:
            ai_analysis = self.analyze_issue(issue)
            
            # Agregar análisis al issue
            issue['ai_analysis'] = ai_analysis['analysis']
            issue['ai_confidence'] = ai_analysis['confidence']
            issue['ai_risk_level'] = ai_analysis['risk_level']
            issue['ai_recommendations'] = ai_analysis['recommendations']
            issue['ai_risk_factors'] = ai_analysis.get('risk_factors', [])
            
            analyzed_issues.append(issue)
        
        return analyzed_issues
    
    def get_statistics(self, issues: List[Dict]) -> Dict:
        """Genera estadísticas de un conjunto de issues"""
        if not issues:
            return {}
        
        total = len(issues)
        critical = sum(1 for i in issues if i.get('ai_risk_level') == 'critical')
        high = sum(1 for i in issues if i.get('ai_risk_level') == 'high')
        medium = sum(1 for i in issues if i.get('ai_risk_level') == 'medium')
        low = sum(1 for i in issues if i.get('ai_risk_level') == 'low')
        
        avg_confidence = sum(i.get('ai_confidence', 0) for i in issues) / total if total > 0 else 0
        
        return {
            'total_issues': total,
            'critical': critical,
            'high': high,
            'medium': medium,
            'low': low,
            'avg_confidence': round(avg_confidence, 2),
            'critical_percentage': round((critical / total) * 100, 2) if total > 0 else 0
        }

