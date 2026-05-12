# Audit Minecraft Plugin (ArgusMC) — Pack48 Round 2

Scope revisado: `minecraft_plugin/argus-mc/src/main/java/**`, `config.yml`, `pom.xml`.

## Resumen ejecutivo

- El plugin muestra buen nivel base de hardening en permisos de comando y separación de checks.
- Riesgos principales actuales: protección de canal plugin->API (sin anti-replay/pinning), exposición de PII en logs/mensajes y potencial evasión por manipulación de timing/lag.
- No se encontraron SQLi directas en plugin (usa HTTP al backend).

## 1) Inputs no validados de packets (PacketEvents listeners)

- **Observación:** `PacketAnticheatListener` procesa múltiples tipos (`PLAYER_*`, `INTERACT_ENTITY`, `DIGGING`) y aplica capturas `try/catch` defensivas.
- **Fortaleza:** evita crash de cadena de listeners por paquete malformado.
- **Riesgo [NEW][MEDIUM]:** ausencia de correlación anti-replay/session-id a nivel plugin puede permitir patrones de evasión con replay controlado en cliente modificado.
- **Recomendación:** introducir indicadores de coherencia temporal por sesión y score de anomalía por burst de packets.

## 2) Autorización `/argus` y subcomandos

- **Verificado:** `onCommand` aplica:
  - `argus.ss.use` para `check/ss/screenshare/scan`.
  - `argus.admin` para `reload/info/test/debug/violations/duda/pregunta`.
- **Conclusión:** no se detectó subcomando admin abierto sin `hasPermission()`.
- **Riesgo residual [LOW]:** regresión futura al agregar subcomandos.
- **Mitigación recomendada:** test unitario que falle si un subcomando nuevo no está en matriz de permisos.

## 3) Logging de PII y privacidad

- **Hallazgo [NEW][MEDIUM]:** el flujo incluye datos de `playerName`, `playerUuid`, detalles de violation y mensajes en chat staff.
- **Impacto:** exposición innecesaria en consola, herramientas de logs y staff no mínimo.
- **Recomendación:** masking parcial de UUID/IP, verbosity por entorno y retención acotada de logs.

## 4) Inyección vía chat events / signed messages

- **Observación:** usa `AsyncPlayerChatEvent` y `PlayerCommandPreprocessEvent` para spam checks.
- **Riesgo [NEW][MEDIUM]:** mensajes no confiables pueden contaminar logs/alertas o telemetry downstream si se reenvían sin sanitización.
- **Mitigación actual:** estructura de checks, whitelists de comandos.
- **Recomendación:** sanitizar/controlar caracteres de control antes de persistencia y envío HTTP.

## 5) Race conditions en `PacketDataStore`

- **Estado actual [FIXED/PARTIAL]:** combina `ConcurrentHashMap`, campos `volatile` y métodos `synchronized` en ventanas críticas.
- **Riesgo residual [LOW/MEDIUM]:**
  - lecturas multi-campo no atómicas en checks complejos.
  - sensibilidad a reordenamiento de eventos entre hilos (Netty vs main thread).
- **Recomendación:** snapshot inmutable por tick para checks que dependan de múltiples campos relacionados.

## 6) Bypass/Evasión factible de anti-cheat

Escenarios plausibles:

1. **Lag spike inducido** para amortiguar thresholds de speed/timer (`MEDIUM`).
2. **Packet replay parcial** en ventanas cortas para confundir secuencia swing/attack (`MEDIUM`).
3. **Micro-burst distribuido** por debajo de thresholds consecutivos (`MEDIUM`).
4. **Abuso de contextos whitelisted** (vehículo/elytra/transiciones) (`MEDIUM`).

Mitigaciones recomendadas:

- score acumulativo por sesión con decay (no solo umbral instantáneo),
- correlación server tick + packet timestamp,
- detección de jitter artificial estadístico.

## 7) Comunicación plugin -> web app

- **Actual:** header `X-Argus-Plugin-Key` sobre HTTPS, timeouts y `User-Agent`.
- **Hallazgo [NEW][HIGH]:** no hay mecanismo anti-replay (nonce/timestamp firmado) ni pinning de certificado en cliente Java.
- **Impacto:** riesgo ante key exfiltrada o escenarios de red comprometida.
- **Recomendación prioritaria:**
  1. HMAC por request (nonce + timestamp + body hash),
  2. expiración corta de request (60-120s),
  3. rotación/revocación frecuente de plugin keys,
  4. opcional mTLS para servidores premium.

## Priorización plugin (Top)

1. **High:** anti-replay/HMAC para API plugin.
2. **Medium:** sanitización y minimización de PII en logs/chat.
3. **Medium:** detección de evasión por jitter/replay.
4. **Low/Medium:** snapshot consistente de estado para evitar edge races.
