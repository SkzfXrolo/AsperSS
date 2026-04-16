"""
Script para convertir consultas SQLite (?) a MySQL (%s) en api_server.py
"""
import re

def convert_placeholders(sql):
    """Convierte placeholders de SQLite (?) a MySQL (%s)"""
    # Contar cuántos ? hay
    count = sql.count('?')
    if count == 0:
        return sql
    
    # Reemplazar ? con %s
    return sql.replace('?', '%s')

def convert_query_in_code(code):
    """Convierte consultas SQL en el código"""
    # Patrón para encontrar consultas SQL con placeholders
    # Busca strings multilinea con ?
    pattern = r"('''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\"|'[^']*'|\"[^\"]*\")"
    
    def replace_sql(match):
        sql = match.group(1)
        # Solo convertir si tiene ? y parece SQL
        if '?' in sql and any(keyword in sql.upper() for keyword in ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WHERE', 'VALUES']):
            return convert_placeholders(sql)
        return sql
    
    return re.sub(pattern, replace_sql, code)

if __name__ == '__main__':
    print("Este script ayuda a convertir consultas SQLite a MySQL")
    print("Ejecuta manualmente las conversiones necesarias")

