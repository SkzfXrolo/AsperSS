"""
Script de migración de SQLite a MySQL
Migra todos los datos de scanner_db.sqlite a MySQL
"""
import sqlite3
import sys
import os
from db_mysql import get_db_connection, init_mysql_db

def migrate_table(sqlite_conn, mysql_conn, table_name, columns, id_column='id'):
    """Migra una tabla de SQLite a MySQL"""
    print(f"📦 Migrando tabla: {table_name}...")
    
    sqlite_cursor = sqlite_conn.cursor()
    mysql_cursor = mysql_conn.cursor()
    
    try:
        # Obtener todos los datos de SQLite
        sqlite_cursor.execute(f'SELECT * FROM {table_name}')
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            print(f"   ⚠️ Tabla {table_name} está vacía, saltando...")
            return 0
        
        # Obtener nombres de columnas
        column_names = [description[0] for description in sqlite_cursor.description]
        
        # Construir query de inserción
        placeholders = ', '.join(['%s'] * len(column_names))
        columns_str = ', '.join([f'`{col}`' for col in column_names])
        insert_query = f'INSERT IGNORE INTO {table_name} ({columns_str}) VALUES ({placeholders})'
        
        # Migrar datos
        migrated_count = 0
        for row in rows:
            try:
                # Convertir row a dict y luego a tuple en el orden correcto
                row_dict = dict(zip(column_names, row))
                values = tuple(row_dict[col] for col in column_names)
                mysql_cursor.execute(insert_query, values)
                migrated_count += 1
            except Exception as e:
                print(f"   ⚠️ Error migrando fila: {e}")
                continue
        
        mysql_conn.commit()
        print(f"   ✅ {migrated_count} filas migradas de {table_name}")
        return migrated_count
        
    except Exception as e:
        print(f"   ❌ Error migrando {table_name}: {e}")
        mysql_conn.rollback()
        return 0
    finally:
        sqlite_cursor.close()

def main():
    """Función principal de migración"""
    print("🚀 Iniciando migración de SQLite a MySQL...")
    print("=" * 60)
    
    # Verificar que existe el archivo SQLite
    sqlite_path = 'scanner_db.sqlite'
    if not os.path.exists(sqlite_path):
        # Intentar en otras ubicaciones
        possible_paths = [
            'source/scanner_db.sqlite',
            'web_app/scanner_db.sqlite',
            os.path.join(os.path.dirname(__file__), 'scanner_db.sqlite'),
            os.path.join(os.path.dirname(__file__), 'source', 'scanner_db.sqlite'),
            os.path.join(os.path.dirname(__file__), 'web_app', 'scanner_db.sqlite'),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                sqlite_path = path
                break
        else:
            print(f"❌ No se encontró scanner_db.sqlite en ninguna ubicación")
            print("   Buscado en:")
            for path in possible_paths:
                print(f"   - {path}")
            return 1
    
    print(f"📁 Archivo SQLite encontrado: {sqlite_path}")
    
    # Conectar a SQLite
    try:
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        print("✅ Conexión a SQLite establecida")
    except Exception as e:
        print(f"❌ Error conectando a SQLite: {e}")
        return 1
    
    # Inicializar MySQL
    try:
        print("\n🔧 Inicializando base de datos MySQL...")
        init_mysql_db()
        mysql_conn = get_db_connection()
        print("✅ Conexión a MySQL establecida")
    except Exception as e:
        print(f"❌ Error conectando a MySQL: {e}")
        print("\n💡 Asegúrate de configurar las variables de entorno:")
        print("   - MYSQL_HOST")
        print("   - MYSQL_PORT")
        print("   - MYSQL_USER")
        print("   - MYSQL_PASSWORD")
        print("   - MYSQL_DATABASE")
        sqlite_conn.close()
        return 1
    
    # Lista de tablas a migrar (en orden de dependencias)
    tables = [
        ('companies', ['id']),
        ('users', ['id']),
        ('scan_tokens', ['id']),
        ('registration_tokens', ['id']),
        ('download_links', ['id']),
        ('scans', ['id']),
        ('ban_history', ['id']),
        ('scan_results', ['id']),
        ('ai_analyses', ['id']),
        ('app_versions', ['id']),
        ('configurations', ['id']),
        ('statistics', ['id']),
        ('staff_feedback', ['id']),
        ('learned_patterns', ['id']),
        ('learned_hashes', ['id']),
        ('ai_model_versions', ['id']),
    ]
    
    print("\n📊 Iniciando migración de datos...")
    print("=" * 60)
    
    total_migrated = 0
    for table_name, id_column in tables:
        try:
            # Verificar que la tabla existe en SQLite
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if not sqlite_cursor.fetchone():
                print(f"⚠️ Tabla {table_name} no existe en SQLite, saltando...")
                sqlite_cursor.close()
                continue
            sqlite_cursor.close()
            
            # Migrar tabla
            count = migrate_table(sqlite_conn, mysql_conn, table_name, [], id_column[0])
            total_migrated += count
        except Exception as e:
            print(f"❌ Error procesando tabla {table_name}: {e}")
            continue
    
    print("=" * 60)
    print(f"✅ Migración completada: {total_migrated} filas migradas en total")
    
    # Cerrar conexiones
    sqlite_conn.close()
    mysql_conn.close()
    
    print("\n🎉 ¡Migración exitosa!")
    print("\n💡 Próximos pasos:")
    print("   1. Verifica que los datos se migraron correctamente")
    print("   2. Actualiza las variables de entorno en Render")
    print("   3. Reinicia los servicios")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

