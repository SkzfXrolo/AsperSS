# Problemas Pendientes - ASPERS Projects SS

## 🟡 Problema Crítico: Resultados de SS no llegan a la aplicación web

**Fecha:** 21 de Noviembre 2025  
**Estado:** 🔍 EN DIAGNÓSTICO - Logging extensivo agregado

**Descripción:**
Los resultados de los escaneos realizados por la aplicación SS (scanner cliente) no están llegando a la aplicación web.

**Soluciones implementadas:**
1. ✅ **Logging extensivo agregado en `source/api_server.py`:**
   - El endpoint `/api/scans/<scan_id>/results` ahora registra:
     - Scan ID recibido
     - IP del cliente
     - Cantidad de resultados recibidos
     - Estado del escaneo en BD
     - Cantidad de resultados insertados
     - Errores detallados con traceback

2. ✅ **Logging mejorado en `source/db_integration.py`:**
   - La función `submit_results()` ahora registra:
     - URL de la API utilizada
     - Scan Token y Scan ID
     - Cantidad de issues y archivos escaneados
     - Respuesta completa de la API
     - Errores de conexión (timeout, connection error, etc.)

3. ✅ **Fallback HTTP en `web_app/app.py`:**
   - Los endpoints `list_scans()` y `get_scan()` ahora:
     - Intentan acceso directo a BD primero (más rápido)
     - Si falla, usan HTTP para obtener datos de la API
     - Funciona correctamente cuando están en servicios separados en Render

**Próximos pasos para diagnosticar:**
1. Ejecutar un escaneo desde la aplicación SS
2. Revisar los logs de Render de la API cuando se envíen resultados
3. Verificar que aparezcan los mensajes de logging:
   - `📥 ===== RECIBIENDO RESULTADOS DE ESCANEO ======`
   - `📤 ===== ENVIANDO RESULTADOS A LA API ======`
4. Si los resultados no llegan, los logs mostrarán exactamente dónde falla

**Notas adicionales:**
- Los tokens ahora se están creando correctamente después de los últimos fixes
- La aplicación SS se conecta a `https://ssapi-cfni.onrender.com`
- La aplicación web está en `https://aspersprojectsss.onrender.com`
- El logging extensivo ayudará a identificar el problema exacto

---

## 🟡 Problema: Datos de pruebas locales no migrados a Render

**Fecha:** 21 de Noviembre 2025  
**Estado:** ✅ SCRIPT DE MIGRACIÓN CREADO

**Descripción:**
La IA no guardó/migró los datos que tenía cargados de cuando se hizo la prueba en local. Los datos de la base de datos local (escaneos, resultados, patrones aprendidos, feedback del staff, etc.) no están disponibles en Render.

**Datos que probablemente se perdieron:**
- Escaneos realizados en local
- Resultados de escaneos
- Patrones aprendidos (`learned_patterns`)
- Hashes aprendidos (`learned_hashes`)
- Feedback del staff (`staff_feedback`)
- Modelos de IA entrenados
- Estadísticas históricas

**Archivos de BD local:**
- `scanner_db.sqlite` - Base de datos de la API (escaneos, resultados, tokens)
- Posiblemente otros archivos de BD en `web_app/` o `source/`

**Solución implementada:**
✅ **Script de migración creado (`migrate_local_data.py`):**
   - Exporta todas las tablas de `scanner_db.sqlite` a archivos JSON
   - Exporta escaneos con sus resultados asociados
   - Crea un resumen de la migración
   - Los datos se guardan en el directorio `migrated_data/`

**Cómo usar el script:**
```bash
python migrate_local_data.py
```

Esto creará archivos JSON en `migrated_data/` con todos los datos exportados.

**Próximos pasos:**
1. Ejecutar `python migrate_local_data.py` para exportar datos locales
2. Revisar los archivos JSON generados en `migrated_data/`
3. Elegir método de importación:
   - **Opción A:** Crear script de importación que lea JSON y los inserte vía API
   - **Opción B:** Migrar a PostgreSQL en Render (recomendado para producción)
   - **Opción C:** Copiar `scanner_db.sqlite` a Render (solo si están en el mismo servicio)

**Nota:** En Render tier gratuito, SQLite puede perder datos al reiniciar el servicio. PostgreSQL es más confiable para producción.

