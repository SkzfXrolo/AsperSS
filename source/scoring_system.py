"""
Sistema de Scoring de Confianza para Resultados de Escaneo
Asigna un score de 0-100 a cada detección basado en múltiples factores
"""
from typing import Dict, List

class ScoringSystem:
    """Sistema de scoring para resultados de escaneo"""
    
    def __init__(self):
        self.factors = {
            'name_match': 30,      # Coincidencia de nombre (30 puntos)
            'location': 20,         # Ubicación del archivo (20 puntos)
            'hash_match': 25,      # Hash conocido (25 puntos)
            'behavior': 15,        # Comportamiento sospechoso (15 puntos)
            'obfuscation': 10      # Ofuscación detectada (10 puntos)
        }
    
    def calculate_score(self, issue: Dict) -> Dict:
        """Calcula el score de confianza para un issue"""
        score = 0
        factors_detail = {}
        
        # Factor 1: Coincidencia de nombre
        name_score = self._score_name_match(issue)
        score += name_score
        factors_detail['name_match'] = name_score
        
        # Factor 2: Ubicación
        location_score = self._score_location(issue)
        score += location_score
        factors_detail['location'] = location_score
        
        # Factor 3: Hash conocido
        hash_score = self._score_hash_match(issue)
        score += hash_score
        factors_detail['hash_match'] = hash_score
        
        # Factor 4: Comportamiento
        behavior_score = self._score_behavior(issue)
        score += behavior_score
        factors_detail['behavior'] = behavior_score
        
        # Factor 5: Ofuscación
        obfuscation_score = self._score_obfuscation(issue)
        score += obfuscation_score
        factors_detail['obfuscation'] = obfuscation_score
        
        # Asegurar que el score esté entre 0 y 100
        score = max(0, min(100, score))
        
        # Determinar nivel de alerta basado en score
        alert_level = self._determine_alert_level(score)
        
        return {
            'score': score,
            'confidence': score / 100.0,  # Convertir a 0-1
            'alert_level': alert_level,
            'factors': factors_detail,
            'interpretation': self._interpret_score(score)
        }
    
    def _score_name_match(self, issue: Dict) -> float:
        """Score basado en coincidencia de nombre - MEJORADO para reducir falsos positivos"""
        name = (issue.get('nombre', '') or '').lower()
        file_path = (issue.get('archivo', '') or '').lower()
        combined = f"{name} {file_path}"
        
        # Patrones de alta confianza (hacks conocidos específicos)
        high_confidence_patterns = [
            'vape', 'vapelite', 'vapev2', 'vapev4', 'entropy', 'entropyclient',
            'killaura', 'aimbot', 'triggerbot', 'reach', 'velocity', 'antiknockback',
            'autoclicker', 'xray', 'scaffold', 'fly', 'nofall', 'speedhack',
            'whiteout', 'liquidbounce', 'wurst', 'impact', 'sigma', 'flux', 'future',
            'astolfo', 'exhibition', 'novoline', 'rise', 'moon', 'drip'
        ]
        
        # Patrones de media confianza (más genéricos)
        medium_confidence_patterns = [
            'bypass', 'inject', 'ghost', 'stealth', 'undetected', 'incognito',
            'hackclient', 'cheatclient', 'injector', 'dllinject'
        ]
        
        # Patrones de baja confianza (muy genéricos - solo si hay contexto adicional)
        low_confidence_patterns = [
            'hack', 'cheat', 'client', 'mod'
        ]
        
        # PATRONES LEGÍTIMOS (reducen score significativamente)
        legitimate_patterns = [
            'optifine', 'forge', 'fabric', 'iris', 'sodium', 'lithium', 'phosphor',
            'jei', 'rei', 'wthit', 'jade', 'worldedit', 'worldguard', 'essentials',
            'luckperms', 'vault', 'curseforge', 'modrinth', 'minecraft launcher',
            'lunar', 'badlion', 'tlauncher', 'prism', 'multimc'
        ]
        
        # Verificar patrones legítimos primero (reducen score)
        for pattern in legitimate_patterns:
            if pattern in combined:
                return -15  # Penalización fuerte para archivos legítimos conocidos
        
        # Verificar patrones de alta confianza
        for pattern in high_confidence_patterns:
            if pattern in combined:
                # Verificar que no sea parte de un nombre legítimo más largo
                if not any(legit in combined for legit in legitimate_patterns):
                    return self.factors['name_match']  # 30 puntos
        
        # Verificar patrones de media confianza
        for pattern in medium_confidence_patterns:
            if pattern in combined:
                # Solo dar puntos si hay contexto adicional sospechoso
                if any(ctx in combined for ctx in ['temp', 'downloads', 'desktop', 'appdata']):
                    return self.factors['name_match'] * 0.6  # 18 puntos
                return self.factors['name_match'] * 0.4  # 12 puntos (menos confianza)
        
        # Verificar patrones de baja confianza (solo con contexto adicional)
        for pattern in low_confidence_patterns:
            if pattern in combined:
                # Requiere contexto adicional para ser sospechoso
                suspicious_context = any(ctx in combined for ctx in [
                    'temp', 'downloads', 'desktop', 'appdata', 'mods\\vape', 'mods\\entropy'
                ])
                if suspicious_context:
                    return self.factors['name_match'] * 0.2  # 6 puntos
                return 0  # Sin contexto adicional, no es sospechoso
        
        return 0
    
    def _score_location(self, issue: Dict) -> float:
        """Score basado en ubicación del archivo"""
        file_path = (issue.get('archivo', '') or '').lower()
        ruta = (issue.get('ruta', '') or '').lower()
        combined = f"{file_path} {ruta}"
        
        # Ubicaciones de alta sospecha
        high_suspicion_locations = [
            'mods\\vape', 'mods\\entropy', 'mods\\sigma', 'mods\\flux',
            'versions\\vape', 'temp', 'downloads', 'desktop',
            'appdata\\local\\temp', 'appdata\\roaming\\.minecraft\\mods'
        ]
        
        # Ubicaciones de media sospecha
        medium_suspicion_locations = [
            'mods', 'versions', 'appdata', 'roaming'
        ]
        
        # Ubicaciones legítimas (reducen score)
        legitimate_locations = [
            'program files', 'program files (x86)', 'windows\\system32'
        ]
        
        # Verificar ubicaciones de alta sospecha
        for location in high_suspicion_locations:
            if location in combined:
                return self.factors['location']  # 20 puntos
        
        # Verificar ubicaciones de media sospecha
        for location in medium_suspicion_locations:
            if location in combined:
                return self.factors['location'] * 0.5  # 10 puntos
        
        # Verificar ubicaciones legítimas (reducen score)
        for location in legitimate_locations:
            if location in combined:
                return -10  # Penalización mayor para reducir falsos positivos
        
        return 0
    
    def _score_hash_match(self, issue: Dict) -> float:
        """Score basado en hash conocido"""
        file_hash = issue.get('file_hash', '')
        hash_known = issue.get('hash_known', False)
        
        if hash_known and file_hash:
            return self.factors['hash_match']  # 25 puntos
        
        return 0
    
    def _score_behavior(self, issue: Dict) -> float:
        """Score basado en comportamiento sospechoso"""
        behavior_score = 0
        
        # Archivo modificado durante escaneo
        if issue.get('modified_during_scan', False):
            behavior_score += 10
        
        # Proceso activo
        if issue.get('is_active_process', False):
            behavior_score += 5
        
        # Inyección detectada
        if issue.get('injection_detected', False):
            behavior_score += 15
        
        return min(behavior_score, self.factors['behavior'])
    
    def _score_obfuscation(self, issue: Dict) -> float:
        """Score basado en ofuscación detectada"""
        obfuscation = issue.get('obfuscation', False)
        obfuscation_detected = issue.get('obfuscation_detected', False)
        
        if obfuscation or obfuscation_detected:
            return self.factors['obfuscation']  # 10 puntos
        
        return 0
    
    def _determine_alert_level(self, score: float) -> str:
        """Determina el nivel de alerta basado en el score"""
        if score >= 80:
            return 'CRITICAL'
        elif score >= 60:
            return 'SOSPECHOSO'
        elif score >= 40:
            return 'POCO_SOSPECHOSO'
        else:
            return 'NORMAL'
    
    def _interpret_score(self, score: float) -> str:
        """Interpreta el score en lenguaje natural"""
        if score >= 90:
            return 'Muy alta probabilidad de hack'
        elif score >= 80:
            return 'Alta probabilidad de hack'
        elif score >= 60:
            return 'Probable hack'
        elif score >= 40:
            return 'Posible hack'
        else:
            return 'Baja probabilidad de hack'
    
    def prioritize_results(self, issues: List[Dict]) -> List[Dict]:
        """Prioriza resultados basado en score"""
        scored_issues = []
        
        for issue in issues:
            scoring_result = self.calculate_score(issue)
            issue['score'] = scoring_result['score']
            issue['confidence'] = scoring_result['confidence']
            issue['alert_level'] = scoring_result['alert_level']
            issue['score_factors'] = scoring_result['factors']
            issue['score_interpretation'] = scoring_result['interpretation']
            scored_issues.append(issue)
        
        # Ordenar por score descendente
        scored_issues.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return scored_issues

