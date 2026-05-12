# Pack48-G Round2: Audit Performance Minecraft Plugin

## Alcance analizado

- `minecraft_plugin/argus-mc/src/main/java/com/argusprojects/argusmc/**`
- Foco en `AnticheatListener`, `PacketAnticheatListener`, `PacketDataStore`, `ViolationManager`, `ArgusApiClient`, `PacketEventsBootstrap`.

## Hallazgos críticos

### 1) Hot path muy cargado en listeners de combate/movimiento
- `PacketAnticheatListener.onPacketPlayReceive` ejecuta múltiples checks por packet.
- `AnticheatListener.onAttack` agrega cálculos geométricos y lógica extensa por evento.

**Riesgo:** impacto TPS en servidores PvP con alta densidad de eventos.

### 2) `resolveEntity` O(N) por ataque packet-based
- En `PacketAnticheatListener`, resolución de entidad por barrido completo de `world.getEntities()`.

**Riesgo:** costo lineal por hit en mundos con muchas entidades.

### 3) Contención de locks por estado de jugador
- `PacketDataStore.State` usa `synchronized` en métodos de alta frecuencia (`pushMove`, `recent*Within`).
- `TimerCheck` también sincroniza sobre el estado.

**Riesgo:** lock contention bajo burst de packets.

### 4) Volumen de logging en rutas activas
- Hay varios `getLogger().info()/warning()` en flujos de enforcement y AI escalation.
- Aunque no son “por tick” puros, en momentos de alta detección generan ruido y I/O.

**Riesgo:** aumento de latencia por I/O de logs en picos.

### 5) Egress HTTP sin batching para violations
- `ArgusApiClient.reportViolationAsync` envía una request por violation.
- AI eval y assistant también son llamadas separadas.

**Riesgo:** presión de red y cola de executor (pool fijo de 2 hilos).

## Sync vs async

- Buen patrón: llamadas HTTP se hacen async (`CompletableFuture`/executor).
- Acciones Bukkit sensibles vuelven al main thread con `runTask` (correcto).
- Aun así, el procesamiento previo en listeners puede consumir budget de tick.

## Memoria por jugador

- `PacketDataStore` usa buffers acotados (`MOVE_BUFFER_SIZE`, etc), buen diseño bounded.
- `AnticheatListener.states` y `ViolationManager.recent` se limpian en quit (correcto).

**Estimación:** razonable, pero conviene perf profile heap en 100+ jugadores.

## Reflection cost (`PacketEventsBootstrap`)

- Reflection se usa principalmente en bootstrap/detección, no en hot path continuo.
- Costo runtime recurrente bajo.

## Target de referencia

- Objetivo operativo: **cero impacto perceptible de TPS** por plugin.
- Objetivo de memoria: **<10MB heap / 100 jugadores** dedicado al plugin.

## Recomendaciones priorizadas

1. **Cache `entityId -> Entity`** (TTL corto) para eliminar `O(N)` por ataque.
2. **Batching HTTP de violations** (flush cada 100-250ms o por tamaño).
3. **Cambiar logs de alta frecuencia a `FINE`** y muestreo de eventos repetitivos.
4. **Reducir sección crítica lockeada** en `PacketDataStore` (ring buffer lock-free o per-tick snapshot).
5. **Executor HTTP configurable** (pool size dinámico según online players).
6. **Métricas internas por check** (tiempo medio/us por check y por packet type).
7. **Cache tipo Caffeine** para lookups repetidos (`player/profile`, traducciones, templates de mensajes).
