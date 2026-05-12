# Pack48-G Performance Audit — Executive Summary

## Contexto

Auditoría estática + bench sintético local sobre:
- Backend Flask (`web_app/app.py`, `argus_ai_*`)
- SQL patterns y schema disponible
- Frontend (`templates` + `static`)
- Scanner desktop (`source/main.py`)
- Plugin Minecraft packet-based (`minecraft_plugin/argus-mc`)

No se modificó código de producción. Solo análisis + recomendaciones.

## Top 5 bottlenecks (impacto estimado)

1. **Escaneo de archivos en desktop totalmente serial + recursivo global**
   - `scan_recent_files` recorre `C:/D:/E:/F:` con `os.walk` completo.
   - Impacto: **muy alto** en latencia end-to-end del scan (2x–10x según tamaño de disco).

2. **Hot path del plugin con `resolveEntity()` O(N entidades) por ataque**
   - En `onPacketPlayReceive` cada `ATTACK` puede iterar todas las entidades del mundo.
   - Impacto: **muy alto** en servers con alta densidad de entidades; puede degradar TPS.

3. **`/api/scans` arma payload grande y hace trabajo extra por request**
   - Lista scans + agrega severidad + segunda pasada para `verdict/risk_score` en Python.
   - Impacto: **alto** bajo polling frecuente de dashboard.

4. **Background jobs duplicables por worker/restart (ML + daily brief)**
   - Gunicorn con 2 workers inicia threads daemon por proceso; riesgo de ejecución duplicada.
   - Impacto: **alto** en carga DB y ruido de jobs.

5. **Frontend polling agresivo + bundle `panel.js` muy grande**
   - Polling cada pocos segundos + bundle ~438 KB sin code splitting.
   - Impacto: **medio-alto** (CPU cliente, ancho de banda y carga API).

## Quick wins (<30 min, impacto alto)

- Reemplazar `resolveEntity(world.getEntities())` por cache `entityId -> Entity` con TTL corto.
- Unificar en SQL parte de enriquecimiento de `/api/scans` (evitar loop O(n^2) para merge por `id`).
- Subir intervalos de polling en `panel.js` cuando pestaña no visible (`document.hidden` backoff).
- Evitar lectura completa de JAR para hashing (`f.read()`), pasar a hash por chunks.
- Guardar guard-lock distribuido para jobs ML/daily (`pg_try_advisory_lock`) y evitar doble ejecución.

## Big rocks (costo mayor, ROI alto)

- **Scanner incremental**: índice local de mtime/hash y re-scan diferencial en vez de full walk.
- **Canal push real-time** para dashboard (SSE/WebSocket) y remover polling periódico masivo.
- **Pipeline ML desacoplado** (worker dedicado/cola) fuera del proceso web de gunicorn.
- **Refactor de consulta de scans** con query única paginada + agregaciones precomputadas/materializadas.
- **Cache externa (Redis)** para stats públicas, dashboard y pesos AI compartidos entre workers.
