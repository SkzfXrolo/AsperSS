"""
Script para importar resultados antiguos de Echo Scanner a ASPERS Projects
"""
import sqlite3
import json
import hashlib
from datetime import datetime
import os
import sys

# Agregar el directorio source al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'source'))

# Configuración
DATABASE = os.path.join(os.path.dirname(__file__), '..', 'source', 'scanner_db.sqlite')

def init_db_if_needed():
    """Inicializa la base de datos si no existe"""
    if not os.path.exists(DATABASE):
        print("⚠️ Base de datos no encontrada. Ejecutando init_db...")
        from api_server import init_db
        init_db()
        print("✅ Base de datos inicializada")

def create_echo_scan(scan_data):
    """
    Crea un escaneo histórico desde datos de Echo
    
    scan_data debe contener:
    {
        'echo_id': 'dab8ea8d-7f75-4a0a-954e-5cf9bdcd14ee',
        'machine_name': 'vgbsmb',
        'os': 'Windows 10 Pro',
        'country': 'Perú',
        'scan_date': '2025-03-XX 19:30:00',  # Fecha del escaneo
        'scan_duration': 129,  # segundos (2m 9s)
        'detections': [
            {
                'name': 'Slinky Client [PU]',
                'location': 'en instancia',
                'severity': 'SEVERO',
                'type': 'client'
            },
            {
                'name': 'Slinky Loader [HS]',
                'location': 'fuera de instancia',
                'file': 'loader.exe',
                'severity': 'SEVERO',
                'type': 'loader'
            },
            # ... más detecciones
        ]
    }
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        # Crear un token histórico (si no existe)
        echo_token = f"ECHO_IMPORT_{scan_data['echo_id'][:8]}"
        cursor.execute('''
            SELECT id FROM scan_tokens WHERE token = ?
        ''', (echo_token,))
        token_result = cursor.fetchone()
        
        if token_result:
            token_id = token_result[0]
        else:
            cursor.execute('''
                INSERT INTO scan_tokens (token, description, created_by, is_active)
                VALUES (?, ?, ?, 1)
            ''', (echo_token, f'Importación histórica de Echo - {scan_data["echo_id"]}', 'echo_importer'))
            token_id = cursor.lastrowid
        
        # Crear el escaneo
        scan_date = datetime.fromisoformat(scan_data['scan_date'].replace(' at ', ' '))
        
        cursor.execute('''
            INSERT INTO scans (
                token_id, scan_token, started_at, completed_at, status,
                total_files_scanned, issues_found, scan_duration,
                machine_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            token_id,
            echo_token,
            scan_date.isoformat(),
            scan_date.isoformat(),
            'completed',
            0,  # No tenemos el total de archivos escaneados
            len(scan_data['detections']),
            scan_data.get('scan_duration', 0),
            scan_data.get('machine_name', 'Unknown')
        ))
        
        scan_id = cursor.lastrowid
        
        # Crear los resultados
        for detection in scan_data['detections']:
            # Determinar nivel de alerta
            alert_level = 'CRITICAL'
            if detection.get('severity') == 'Alerta':
                alert_level = 'SOSPECHOSO'
            elif detection.get('severity') == 'Limpio':
                alert_level = 'POCO_SOSPECHOSO'
            
            # Construir nombre del issue
            issue_name = detection.get('name', 'Detección desconocida')
            if detection.get('file'):
                issue_name = f"{issue_name} - {detection['file']}"
            
            # Construir ruta
            issue_path = detection.get('location', '')
            if detection.get('file'):
                issue_path = f"{issue_path}/{detection['file']}" if issue_path else detection['file']
            
            # Detectar patrones comunes
            detected_patterns = []
            name_lower = issue_name.lower()
            
            if 'slinky' in name_lower:
                detected_patterns.append('slinky')
            if 'loader' in name_lower:
                detected_patterns.append('loader')
            if 'client' in name_lower:
                detected_patterns.append('client')
            
            # Calcular hash del nombre+ruta para identificación
            file_hash = hashlib.md5(f"{issue_name}{issue_path}".encode()).hexdigest()
            
            cursor.execute('''
                INSERT INTO scan_results (
                    scan_id, issue_type, issue_name, issue_path,
                    issue_category, alert_level, confidence,
                    detected_patterns, obfuscation_detected, file_hash,
                    ai_analysis, ai_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                scan_id,
                detection.get('type', 'unknown'),
                issue_name,
                issue_path,
                'echo_import',
                alert_level,
                85.0 if alert_level == 'CRITICAL' else 60.0,
                json.dumps(detected_patterns),
                False,
                file_hash,
                f"Importado desde Echo Scanner. Detección: {detection.get('name', 'Desconocida')}",
                80.0
            ))
        
        conn.commit()
        print(f"✅ Escaneo importado exitosamente:")
        print(f"   - Scan ID: {scan_id}")
        print(f"   - Echo ID: {scan_data['echo_id']}")
        print(f"   - Detecciones: {len(scan_data['detections'])}")
        print(f"   - Fecha: {scan_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return scan_id
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error importando escaneo: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        conn.close()

def import_from_text():
    """Importa resultados desde texto copiado de Echo"""
    print("=" * 60)
    print("  IMPORTADOR DE RESULTADOS ECHO A ASPERS PROJECTS")
    print("=" * 60)
    print()
    
    # Datos del ejemplo proporcionado
    scan_data = {
        'echo_id': input("ID del escaneo de Echo (o presiona Enter para usar ejemplo): ").strip() or 'dab8ea8d-7f75-4a0a-954e-5cf9bdcd14ee',
        'machine_name': input("Nombre de la máquina (o presiona Enter para 'vgbsmb'): ").strip() or 'vgbsmb',
        'os': input("Sistema operativo (o presiona Enter para 'Windows 10 Pro'): ").strip() or 'Windows 10 Pro',
        'country': input("País (o presiona Enter para 'Perú'): ").strip() or 'Perú',
        'scan_date': input("Fecha del escaneo (formato: 2025-03-XX 19:30:00 o presiona Enter para ahora): ").strip() or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'scan_duration': int(input("Duración del escaneo en segundos (o presiona Enter para 129): ").strip() or '129'),
        'detections': []
    }
    
    print()
    print("Ingresa las detecciones (presiona Enter sin texto para terminar):")
    print("Formato: Nombre | Ubicación | Severidad | Tipo")
    print("Ejemplo: Slinky Client [PU] | en instancia | SEVERO | client")
    print()
    
    detection_num = 1
    while True:
        detection_input = input(f"Detección {detection_num}: ").strip()
        if not detection_input:
            break
        
        parts = [p.strip() for p in detection_input.split('|')]
        if len(parts) < 2:
            print("⚠️ Formato incorrecto. Usa: Nombre | Ubicación | Severidad | Tipo")
            continue
        
        detection = {
            'name': parts[0],
            'location': parts[1] if len(parts) > 1 else '',
            'severity': parts[2] if len(parts) > 2 else 'SEVERO',
            'type': parts[3] if len(parts) > 3 else 'unknown'
        }
        
        # Extraer nombre de archivo si está en el nombre
        if '.exe' in detection['name']:
            detection['file'] = detection['name'].split()[-1]
        
        scan_data['detections'].append(detection)
        detection_num += 1
    
    if not scan_data['detections']:
        # Usar detecciones del ejemplo
        print("\n⚠️ No se ingresaron detecciones. Usando ejemplo del escaneo proporcionado...")
        scan_data['detections'] = [
            {
                'name': 'Slinky Client [PU]',
                'location': 'en instancia',
                'severity': 'SEVERO',
                'type': 'client'
            },
            {
                'name': 'Slinky Loader [HS]',
                'location': 'fuera de instancia',
                'file': 'loader.exe',
                'severity': 'SEVERO',
                'type': 'loader'
            },
            {
                'name': 'Slinky Loader [HS]',
                'location': 'en instancia',
                'file': 'loader.exe',
                'severity': 'SEVERO',
                'type': 'loader'
            },
            {
                'name': 'Servicio SysMain',
                'location': 'detenido manualmente',
                'severity': 'Alerta',
                'type': 'service'
            }
        ]
    
    print()
    print("=" * 60)
    print("  RESUMEN DEL ESCANEO A IMPORTAR")
    print("=" * 60)
    print(f"Echo ID: {scan_data['echo_id']}")
    print(f"Máquina: {scan_data['machine_name']}")
    print(f"OS: {scan_data['os']}")
    print(f"Fecha: {scan_data['scan_date']}")
    print(f"Detecciones: {len(scan_data['detections'])}")
    print()
    for i, det in enumerate(scan_data['detections'], 1):
        print(f"  {i}. {det['name']} - {det.get('location', 'N/A')} ({det['severity']})")
    print()
    
    confirm = input("¿Importar este escaneo? (s/n): ").strip().lower()
    if confirm != 's':
        print("❌ Importación cancelada")
        return
    
    init_db_if_needed()
    scan_id = create_echo_scan(scan_data)
    
    if scan_id:
        print()
        print("=" * 60)
        print("  ✅ IMPORTACIÓN COMPLETADA")
        print("=" * 60)
        print(f"Puedes ver el escaneo en el panel web con ID: {scan_id}")
        print(f"O accede directamente a: http://localhost:8080/panel")
    else:
        print()
        print("=" * 60)
        print("  ❌ ERROR EN LA IMPORTACIÓN")
        print("=" * 60)

def import_from_json_file(json_file):
    """Importa desde un archivo JSON con múltiples escaneos"""
    with open(json_file, 'r', encoding='utf-8') as f:
        scans = json.load(f)
    
    if not isinstance(scans, list):
        scans = [scans]
    
    init_db_if_needed()
    
    imported = 0
    failed = 0
    
    for scan_data in scans:
        scan_id = create_echo_scan(scan_data)
        if scan_id:
            imported += 1
        else:
            failed += 1
    
    print()
    print("=" * 60)
    print("  RESUMEN DE IMPORTACIÓN")
    print("=" * 60)
    print(f"✅ Importados: {imported}")
    print(f"❌ Fallidos: {failed}")
    print(f"📊 Total: {len(scans)}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Importar desde archivo JSON
        json_file = sys.argv[1]
        if os.path.exists(json_file):
            import_from_json_file(json_file)
        else:
            print(f"❌ Archivo no encontrado: {json_file}")
    else:
        # Modo interactivo
        import_from_text()

