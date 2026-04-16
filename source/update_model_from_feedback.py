"""
Script para actualizar el modelo de IA con patrones aprendidos
Se ejecuta automáticamente cuando el staff marca suficientes hacks
"""
import sqlite3
import json
import os
import sys
from datetime import datetime

def update_model_from_feedback():
    """Actualiza el modelo de IA con los patrones aprendidos"""
    DATABASE = 'scanner_db.sqlite'
    
    if not os.path.exists(DATABASE):
        print("❌ Base de datos no encontrada")
        return False
    
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Obtener patrones aprendidos
    cursor.execute('''
        SELECT pattern_value, pattern_category, confidence
        FROM learned_patterns
        WHERE is_active = 1
        ORDER BY learned_from_count DESC
    ''')
    learned_patterns = cursor.fetchall()
    
    # Obtener hashes aprendidos
    cursor.execute('''
        SELECT file_hash FROM learned_hashes WHERE is_hack = 1
    ''')
    learned_hashes = [row[0] for row in cursor.fetchall()]
    
    # Contar feedbacks
    cursor.execute('SELECT COUNT(*) FROM staff_feedback')
    feedback_count = cursor.fetchone()[0]
    
    conn.close()
    
    # Generar archivo de actualización del modelo
    model_update = {
        'version': f"1.{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'patterns': {
            'high_risk': [p[0] for p in learned_patterns if p[1] == 'high_risk'],
            'medium_risk': [p[0] for p in learned_patterns if p[1] == 'medium_risk'],
            'low_risk': [p[0] for p in learned_patterns if p[1] == 'low_risk']
        },
        'hashes': learned_hashes,
        'updated_at': datetime.now().isoformat(),
        'feedback_count': feedback_count
    }
    
    # Guardar modelo actualizado
    os.makedirs('models', exist_ok=True)
    model_file = f'models/ai_model_{model_update["version"]}.json'
    
    with open(model_file, 'w', encoding='utf-8') as f:
        json.dump(model_update, f, indent=2)
    
    print(f"✅ Modelo actualizado guardado en: {model_file}")
    print(f"📊 Patrones aprendidos: {len(learned_patterns)}")
    print(f"🔐 Hashes aprendidos: {len(learned_hashes)}")
    print(f"📝 Feedbacks totales: {feedback_count}")
    
    return True

if __name__ == '__main__':
    update_model_from_feedback()

