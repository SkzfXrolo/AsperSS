"""Esquema mínimo de las tablas de aprendizaje local (learned_hashes/learned_patterns).

legitimate_patterns.py y ai_analyzer.py leen/escriben estas tablas asumiendo que
ya existen (las crea api_server.py, que solo corre en el panel hosteado — el
scanner standalone nunca las ve, así que cada scan tiraba "no such table" 3
veces). Se centraliza acá para que ambos módulos usen el mismo esquema en vez
de definirlo cada uno por su lado (legitimate_patterns.py necesita columnas
is_active/learned_from que el esquema de api_server.py no tiene).
"""
import sqlite3


def ensure_learning_tables(conn: sqlite3.Connection) -> None:
    """Crea learned_hashes/learned_patterns si no existen. Idempotente."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learned_hashes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT UNIQUE NOT NULL,
            is_hack BOOLEAN NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            learned_from TEXT,
            confirmed_count INTEGER DEFAULT 1,
            first_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_feedback_id INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learned_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT,
            pattern_value TEXT NOT NULL,
            pattern_category TEXT,
            confidence REAL DEFAULT 1.0,
            is_active BOOLEAN DEFAULT 1,
            first_learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
