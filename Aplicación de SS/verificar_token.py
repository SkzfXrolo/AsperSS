"""
Script para verificar si un token existe en la base de datos
"""
import sqlite3
import sys

if len(sys.argv) < 2:
    print("Uso: python verificar_token.py <token>")
    

token = sys.argv[1]
db_path = 'scanner_db.sqlite'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, token, created_at, expires_at, used_count, max_uses, is_active, description
        FROM scan_tokens
        WHERE token = ?
    ''', (token,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        token_id, token_val, created_at, expires_at, used_count, max_uses, is_active, description = result
        print(f"✅ Token encontrado en la base de datos:")
        print(f"   ID: {token_id}")
        print(f"   Creado: {created_at}")
        print(f"   Expira: {expires_at or 'Nunca'}")
        print(f"   Usos: {used_count} / {max_uses if max_uses > 0 else 'Ilimitado'}")
        print(f"   Activo: {'Sí' if is_active else 'No'}")
        print(f"   Descripción: {description or 'N/A'}")
        
        if not is_active:
            print("\n❌ El token está DESACTIVADO")
        elif expires_at:
            from datetime import datetime
            expires = datetime.fromisoformat(expires_at)
            if datetime.now() > expires:
                print("\n❌ El token ha EXPIRADO")
            else:
                print(f"\n✅ El token es válido y no ha expirado")
        else:
            print(f"\n✅ El token es válido (sin fecha de expiración)")
            
        if max_uses > 0 and used_count >= max_uses:
            print(f"\n❌ El token ha alcanzado el límite de usos ({max_uses})")
    else:
        print(f"❌ Token NO encontrado en la base de datos")
        print(f"\n💡 Verifica que:")
        print(f"   1. El token fue copiado correctamente")
        print(f"   2. El token fue generado desde el panel web")
        print(f"   3. La base de datos está en: {db_path}")
        
except Exception as e:
    print(f"❌ Error al verificar token: {e}")
    import traceback
    traceback.print_exc()

