# Pack48-G Performance Findings (detallado)

## Backend

### B1 — `/api/scans` hace trabajo múltiple por request + merge ineficiente
- **Referencia:** `web_app/app.py` (`list_scans`, bloque query principal y merge posterior).
- **Descripción:** consulta principal + agregación severidad + segunda consulta de `verdict/risk_score`; luego merge por loops Python.
- **Impacto estimado:** alto con alto cardinal de scans y polling continuo.
- **Recomendación:** resolver columnas necesarias en una sola query y usar mapa `id -> row`.
- **Snippet fix:**
```python
verdict_map = {r["id"]: r for r in cursor.fetchall()}
for s in scans:
    v = verdict_map.get(s["id"])
    if v:
        s["verdict"] = v["verdict"]
```

### B2 — Jobs daemon arrancan por worker y se duplican
- **Referencia:** `web_app/app.py` (`threading.Thread(..._ml_background_loop).start()`, idem daily brief).
- **Descripción:** con gunicorn multi-worker cada proceso arranca loops propios.
- **Impacto estimado:** alto en DB load y retrains redundantes.
- **Recomendación:** lock distribuido (advisory lock) o mover jobs a worker único.
- **Snippet fix:**
```python
cursor.execute("SELECT pg_try_advisory_lock(48001)")
if not cursor.fetchone()[0]:
    return  # otro worker ya ejecuta el job
```

### B3 — `_train_models_for` crece casi lineal y entrena siempre 3 modelos
- **Referencia:** `web_app/app.py` (`_train_models_for`), `web_app/argus_ai_trainer.py`.
- **Descripción:** LR `fit` O(n * epochs * f), KNN inserta O(n), temporal agrega muestras fijas.
- **Impacto estimado:** medio-alto; crece rápido con datasets grandes.
- **Recomendación:** early-stop + max cap por company + entrenamiento incremental.

### B4 — `evaluate_hybrid` depende de KNN O(m) por inferencia
- **Referencia:** `web_app/argus_ai_oracle.py` + `argus_ai_trainer.py` (`ensemble_predict` / KNN).
- **Descripción:** similitud contra ejemplos KNN en cada evaluación.
- **Impacto estimado:** medio (sube con tamaño de histórico KNN).
- **Recomendación:** cap de ejemplos por recencia/confianza o ANN.

### B5 — `SELECT *` en perfil AI trae payload completo
- **Referencia:** `web_app/app.py` (`SELECT * FROM ai_player_profiles ...`).
- **Descripción:** selecciona todo cuando solo se usan pocos campos.
- **Impacto estimado:** medio por transferencia y decode JSON.
- **Recomendación:** proyectar columnas puntuales.

## DB

### D1 — Patrones de ORDER BY sin índice compuesto ideal
- **Referencia:** queries por `ORDER BY started_at DESC`, `created_at DESC`, `score DESC`.
- **Descripción:** hay índices parciales, pero faltan compuestos por filtros frecuentes.
- **Impacto estimado:** alto en tablas grandes.
- **Recomendación:** índices compuestos (ver `index-recommendations.sql`).

### D2 — `IN (...)` dinámicos con listas grandes
- **Referencia:** `scan_id IN ({placeholders})`, `player_uuid IN (...)`, `fingerprint IN (...)`.
- **Descripción:** para lotes grandes, planner puede degradar.
- **Impacto estimado:** medio.
- **Recomendación:** usar temp table / `UNNEST` + JOIN para lotes grandes.

### D3 — Múltiples `COUNT(*)` separados para estadísticas
- **Referencia:** endpoints estadísticas (`/api/statistics`, `/api/dashboard/extended`).
- **Descripción:** varios round-trips en lugar de agregación consolidada.
- **Impacto estimado:** medio.
- **Recomendación:** agrupar métricas en una query con CTE/agregaciones.

### D4 — Índices de `ai_maintenance.suggest_db_indexes` son base, no cubren casos plugin/reportes
- **Referencia:** `web_app/ai_maintenance.py`.
- **Descripción:** sugerencias actuales son buenas pero incompletas para rutas Pack 45-48.
- **Impacto estimado:** medio-alto.
- **Recomendación:** complementar con 15-20 índices adicionales (archivo SQL).

## Frontend

### F1 — Polling periódico sin adaptación agresiva
- **Referencia:** `web_app/static/js/panel.js` (`setInterval`, múltiples `fetch`).
- **Descripción:** polling de scans + running + dashboard en paralelo.
- **Impacto estimado:** alto en API bajo muchas sesiones.
- **Recomendación:** backoff por visibilidad/tab hidden y jitter.

### F2 — Bundle JS principal grande
- **Referencia:** `web_app/static/js/panel.js` (~438,438 bytes).
- **Descripción:** lógica de dashboard, modales, IA, admin y UX en un único archivo.
- **Impacto estimado:** medio-alto en TTI/parse time.
- **Recomendación:** split por feature (dashboard, scan detail, admin).

### F3 — Tabla con render completo de filas (sin virtualización)
- **Referencia:** `web_app/templates/panel.html` (`results-table-body`).
- **Descripción:** inserción DOM de listas grandes.
- **Impacto estimado:** medio en equipos low-end.
- **Recomendación:** virtualizar filas (windowing) y paginar más agresivo.

### F4 — Asset pesado no optimizado
- **Referencia:** `web_app/static/img/logo.png` (~836,200 bytes).
- **Descripción:** PNG único grande.
- **Impacto estimado:** medio en cold load móvil.
- **Recomendación:** exportar WebP/AVIF + `srcset`.

## Scanner desktop

### S1 — `scan_recent_files` recorre discos completos
- **Referencia:** `source/main.py` (`scan_recent_files`).
- **Descripción:** `os.walk` sin pruning global de C:/D:/E:/F:.
- **Impacto estimado:** muy alto.
- **Recomendación:** limitar roots + cache incremental por mtime.

### S2 — Lecturas completas en memoria para hashing/fingerprint
- **Referencia:** `source/main.py` (`sha1(f.read())`, `raw = f.read()`).
- **Descripción:** carga archivos completos en RAM.
- **Impacto estimado:** alto para JAR grandes.
- **Recomendación:** hash/chunked read.
- **Snippet fix:**
```python
h = hashlib.sha1()
with open(path, "rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        h.update(chunk)
sha1 = h.hexdigest()
```

### S3 — Falta paralelismo estructurado en scans de filesystem
- **Referencia:** múltiples `scan_*` secuenciales.
- **Descripción:** gran parte del workload IO-bound corre serial.
- **Impacto estimado:** medio-alto.
- **Recomendación:** `ThreadPoolExecutor` por roots + límite de workers.

## Plugin Minecraft

### P1 — `onPacketPlayReceive` muy cargado por packet
- **Referencia:** `PacketAnticheatListener.onPacketPlayReceive`.
- **Descripción:** múltiples checks por packet + acceso Bukkit + scheduling.
- **Impacto estimado:** alto en PvP intenso.
- **Recomendación:** short-circuit por estado/cooldown y sampling en checks caros.

### P2 — `resolveEntity` O(N) por ataque
- **Referencia:** `PacketAnticheatListener.resolveEntity`.
- **Descripción:** iteración completa de `world.getEntities()`.
- **Impacto estimado:** muy alto en mundos poblados.
- **Recomendación:** cache `entityId -> Entity` o resolver vía API packet-level.

### P3 — `String.format` en paths frecuentes
- **Referencia:** checks packet (`StepCheck`, `VClipCheck`, `CPSPacketCheck`, etc.).
- **Descripción:** formateo de strings aun cuando el sink puede no usar detalle completo.
- **Impacto estimado:** medio.
- **Recomendación:** lazy formatting o `StringBuilder` simple en hot path.

### P4 — Contención por `synchronized` en `PacketDataStore.State`
- **Referencia:** `PacketDataStore` (`push*`, `recent*Within`).
- **Descripción:** locks por jugador en alta frecuencia de packets.
- **Impacto estimado:** medio-alto.
- **Recomendación:** estructuras lock-free acotadas o snapshots por tick.
