"""
Script para migrar datos de la base de datos local a Render
Exporta datos de scanner_db.sqlite local y los prepara para importar en Render

Uso:
    python migrate_local_data.py

Esto creará archivos JSON con los datos exportados que luego se pueden importar
usando un script de importación o directamente vía API.
"""
import sqlite3
import json
import os
from datetime import datetime

# Rutas de las bases de datos
LOCAL_DB_PATH = os.path.join('source', 'scanner_db.sqlite')
OUTPUT_DIR = 'migrated_data'

def ensure_output_dir():
    """Crea el directorio de salida si no existe"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"✅ Directorio creado: {OUTPUT_DIR}")

def export_table(cursor, table_name, output_file):
    """Exporta una tabla completa a JSON"""
    try:
        cursor.execute(f'SELECT * FROM {table_name}')
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Convertir tipos especiales
                if isinstance(value, bytes):
                    value = value.hex()  # Convertir bytes a hex string
                elif isinstance(value, datetime):
                    value = value.isoformat()
                row_dict[col] = value
            data.append(row_dict)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ Exportados {len(data)} registros de {table_name} → {output_file}")
        return len(data)
    except Exception as e:
        print(f"⚠️ Error exportando {table_name}: {e}")
        return 0

def export_scans_and_results(cursor, output_file):
    """Exporta escaneos con sus resultados asociados"""
    try:
        cursor.execute('''
            SELECT id, token_id, scan_token, started_at, completed_at, status,
                   total_files_scanned, issues_found, scan_duration, machine_id, 
                   machine_name, ip_address, country, minecraft_username
            FROM scans
            ORDER BY started_at DESC
        ''')
        
        scans = []
        columns = [description[0] for description in cursor.description]
        
        for row in cursor.fetchall():
            scan_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, datetime):
                    value = value.isoformat()
                scan_dict[col] = value
            
            scan_id = scan_dict['id']
            
            # Obtener resultados de este escaneo
            cursor.execute('''
                SELECT id, issue_type, issue_name, issue_path, issue_category,
                       alert_level, confidence, detected_patterns, obfuscation_detected,
                       file_hash, ai_analysis, ai_confidence
                FROM scan_results
                WHERE scan_id = ?
            ''', (scan_id,))
            
            results = []
            result_columns = [description[0] for description in cursor.description]
            for result_row in cursor.fetchall():
                result_dict = {}
                for i, col in enumerate(result_columns):
                    value = result_row[i]
                    if isinstance(value, bytes):
                        value = value.hex()
                    elif isinstance(value, datetime):
                        value = value.isoformat()
                    elif col == 'detected_patterns' and value:
                        try:
                            value = json.loads(value) if isinstance(value, str) else value
                        except:
                            pass
                    result_dict[col] = value
                results.append(result_dict)
            
            scan_dict['results'] = results
            scans.append(scan_dict)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(scans, f, indent=2, ensure_ascii=False, default=str)
        
        total_results = sum(len(s['results']) for s in scans)
        print(f"✅ Exportados {len(scans)} escaneos con {total_results} resultados → {output_file}")
        return len(scans)
    except Exception as e:
        print(f"⚠️ Error exportando escaneos: {e}")
        import traceback
        traceback.print_exc()
        return 0

def main():
    """Función principal de migración"""
    print("="*60)
    print("📦 MIGRACIÓN DE DATOS LOCALES A RENDER")
    print("="*60)
    print()
    
    # Verificar que existe la BD local
    if not os.path.exists(LOCAL_DB_PATH):
        print(f"❌ Error: No se encontró la base de datos local en {LOCAL_DB_PATH}")
        print("💡 Asegúrate de que el archivo existe antes de ejecutar la migración")
        return
    
    print(f"📂 Base de datos local: {LOCAL_DB_PATH}")
    
    # Crear directorio de salida
    ensure_output_dir()
    
    # Conectar a la BD local
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        print("✅ Conectado a la base de datos local")
    except Exception as e:
        print(f"❌ Error conectando a la BD: {e}")
        return
    
    print()
    print("📤 Exportando datos...")
    print("-"*60)
    
    # Exportar tablas principales
    tables_to_export = [
        'scan_tokens',
        'ban_history',
        'staff_feedback',
        'learned_patterns',
        'learned_hashes',
        'app_versions',
        'ai_model_versions',
        'configurations'
    ]
    
    total_exported = 0
    
    for table in tables_to_export:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            if count > 0:
                output_file = os.path.join(OUTPUT_DIR, f"{table}.json")
                exported = export_table(cursor, table, output_file)
                total_exported += exported
            else:
                print(f"⏭️  {table}: Sin datos (0 registros)")
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                print(f"⏭️  {table}: Tabla no existe")
            else:
                print(f"⚠️  Error en {table}: {e}")
    
    # Exportar escaneos con resultados (estructura especial)
    print()
    print("📤 Exportando escaneos con resultados...")
    scans_file = os.path.join(OUTPUT_DIR, "scans_with_results.json")
    exported_scans = export_scans_and_results(cursor, scans_file)
    total_exported += exported_scans
    
    # Crear archivo de resumen
    summary = {
        'export_date': datetime.now().isoformat(),
        'source_db': LOCAL_DB_PATH,
        'tables_exported': tables_to_export,
        'total_records': total_exported,
        'scans_exported': exported_scans,
        'output_directory': OUTPUT_DIR
    }
    
    summary_file = os.path.join(OUTPUT_DIR, "migration_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    conn.close()
    
    print()
    print("="*60)
    print("✅ MIGRACIÓN COMPLETADA")
    print("="*60)
    print(f"📊 Total de registros exportados: {total_exported}")
    print(f"📁 Archivos guardados en: {OUTPUT_DIR}/")
    print()
    print("📝 PRÓXIMOS PASOS:")
    print("1. Revisa los archivos JSON en el directorio 'migrated_data'")
    print("2. Para importar en Render:")
    print("   - Opción A: Usar un script de importación que lea estos JSON y los inserte vía API")
    print("   - Opción B: Migrar directamente a PostgreSQL en Render (recomendado)")
    print("   - Opción C: Copiar scanner_db.sqlite a Render (solo si están en el mismo servicio)")
    print()
    print("⚠️  NOTA: En Render con servicios separados, SQLite puede perder datos.")
    print("   Se recomienda migrar a PostgreSQL para producción.")

if __name__ == '__main__':
    main()

