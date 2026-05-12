# Argus MC — Deployment Guide

Guía para deployar Argus MC en producción.

## Requisitos

| Componente            | Mínimo            | Recomendado            |
|-----------------------|-------------------|-------------------------|
| Server software       | Paper 1.20.x      | Paper 1.21.3            |
| JDK                   | 17                | 21                       |
| RAM (server)          | 2 GB              | 4 GB                     |
| RAM (Argus overhead)  | ~50 MB            | ~80 MB                   |
| CPU                   | 1 vCPU            | 2 vCPU                   |
| Backend Argus         | Opcional          | Sí (para Discord/Web)    |

## Compatibilidad MC versions

Ver `COMPAT.md`. Soportado oficialmente Paper 1.20.4 → 1.21.3. Spigot
funciona pero con limitaciones (sin Paper-specific APIs como `getPing()`
nativo, brand detection, etc.).

## Quick start (sin backend)

1. Descargar el JAR (último estable) de `/argus-mc-X.Y.Z.jar`.
2. Copiarlo a `<server>/plugins/`.
3. Iniciar el server. Argus crea `plugins/ArgusMC/config.yml`.
4. Por defecto el plugin va en **observer mode** (sin enforcement).
   Esto te da 24h para tunear sin bannear nadie por error.
5. `/argus version` confirma que está activo.

## Quick start (con backend Argus)

1. Tener una instancia Argus corriendo (web_app). Por ejemplo,
   `https://miargus.com`.
2. Crear API key desde `/aspers-sa` → "Plugin Keys Minecraft".
3. Pegar la key en `config.yml`:

   ```yaml
   api:
     base_url: "https://miargus.com"
     key: "argus_pk_..."
   ```

4. Reload con `/argus reload`.
5. Confirmar conexión: `/argus admin stats`.

## Deployment scenarios

### Single server (paper)

```
- plugins/
  - ArgusMC.jar
  - PacketEvents.jar    # opcional, mejor performance
- config.yml             # tu config
```

### Paper detrás de Velocity/BungeeCord

- Argus va **dentro** del paper, no en el proxy.
- En cada backend node, mismo `config.yml`.
- Backend Argus puede recibir alerts de N nodos sin overlap (cada uno
  envía con su server_id).
- Si querés "soft kick" (a lobby), configurar:

  ```yaml
  enforcement:
    kick_message: "&cExpulsión por anti-cheat. /lobby para volver."
  ```

  Y en el proxy configurar `try` para redirigir.

### Multi-node con Argus backend único

```
[proxy]    →   [paper-1, paper-2, paper-3] → cada uno con Argus →
              ↓
              [Argus backend] ←→ [Argus Web] ←→ Staff Discord
```

Todos los logs / violations agregadas en un solo backend. Recomendado.

## Web Dashboard

OFF por defecto. Para activar:

```yaml
web:
  enabled: true
  port: 8765
  api_key: "REEMPLAZA_LARGO_SECRETO"
  ip_allowlist: ["127.0.0.1", "::1"]
```

Abrir túnel SSH: `ssh -L 8765:localhost:8765 user@server` →
`http://localhost:8765/` desde local.

### HTTPS opcional

Generá keystore:

```
keytool -genkeypair -alias argus -keyalg RSA -keysize 2048 \
    -keystore plugins/ArgusMC/argus-keystore.p12 -storetype PKCS12 \
    -validity 365 -storepass UN_SECRETO
```

Config:

```yaml
web:
  enabled: true
  https:
    enabled: true
    keystore_path: "plugins/ArgusMC/argus-keystore.p12"
    keystore_password: "UN_SECRETO"
```

## Prometheus / Grafana

Si tenés Grafana, activá `/metrics`:

```yaml
web:
  enabled: true
  public_metrics: true    # /metrics no requiere api_key
```

Scrape config (prometheus.yml):

```yaml
scrape_configs:
  - job_name: argus-mc
    static_configs:
      - targets: ['mc-server:8765']
```

Métricas relevantes:
- `argus_violations_total{check,level}` — counter total.
- `argus_packets_received_total` — packets per second (rate).
- `argus_oracle_calls_total` — calls al Oracle.

## bStats (opcional, anonymous)

Activado por default. Solo manda: número de players, plugin version,
checks activos. Si no querés telemetría:

```yaml
metrics:
  enabled: false
```

## Backup / migration

- `config.yml` → versioná (git, etc).
- No hay state local persistente — Argus está stateless en cuanto a
  violations (todo va al backend).
- Si migrás de servidor, copiá solo `config.yml`.

## Rollback

Si una versión nueva rompe algo:

1. Detener el server.
2. Reemplazar el JAR por la versión anterior.
3. **NO tocar `config.yml`** salvo que el changelog diga lo contrario.
4. Iniciar.

## Performance check post-deploy

```
/argus admin stats         # ver counters
/timings on (15m)          # paper
/timings paste             # subir a paper timings
```

Argus debería aparecer < 1% del CPU del servidor. Si está más alto:

1. Comprobar que `tuning.lag_compensation` esté ON.
2. Desactivar checks "advanced" que no aplican a tu modalidad
   (ej: `tracers` en server sin invis).
3. Reportar timings via issue.

## Hardening

- Cambiar `web.api_key` a algo aleatorio (32+ chars).
- `ip_allowlist` solo loopback en prod, abrir solo para
  Grafana/Prometheus IP.
- Activar `web.https` con cert.
- Permisos LuckPerms: solo dar `argus.admin` a staff confiable.
- Permiso `argus.ac.bypass`: NUNCA a staff común — solo a owner que
  necesita debugear en creative.

## Soporte

- Logs en `logs/latest.log` con prefijo `[Argus]`.
- Issues: `https://github.com/argusprojects/argus-mc/issues` (placeholder).
- Discord: ver web_app.
