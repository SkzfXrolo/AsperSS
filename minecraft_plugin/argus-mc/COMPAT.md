# Argus MC — Compatibility Matrix

> Pack 48 round 2 — Version compat table + soft-deps + proxy notes.

## Supported Minecraft versions

El plugin se compila contra **paper-api 1.21.3** pero declara `api-version: '1.19'`
en `plugin.yml`. Solo usa APIs Bukkit estables desde 1.13, así que el .jar
resultante corre en cualquier servidor compatible con la API Bukkit moderna.

| MC version | Bukkit / Paper API | Soportado | Notas |
|------------|--------------------|-----------|-------|
| 1.8.x      | -                  | ❌ no      | Requiere recompilación con `paper-api 1.16` y eliminación de APIs nuevas (`Player#getPing`, `getBoundingBox`, `isCritical`). |
| 1.9 – 1.12 | -                  | ⚠️ limitado | Funciona sin checks que dependan de `getBoundingBox()` (1.13+). KillauraBlocking detecta sword raised por `isBlocking()`. |
| 1.13       | -                  | ✅ ok      | Limites inferiores oficiales: `api-version: 1.13`. |
| 1.14       | -                  | ✅ ok      | -     |
| 1.15       | -                  | ✅ ok      | -     |
| 1.16       | -                  | ✅ ok      | -     |
| 1.17       | -                  | ✅ ok      | Java 16+ requerido en server. |
| 1.18       | -                  | ✅ ok      | -     |
| 1.19       | 1.19.4             | ✅ ok      | Limite "official" del plugin. |
| 1.20.x     | 1.20.4             | ✅ ok      | Probado en Aternos con Spigot 1.20.1 y Paper 1.20.4. |
| 1.21.x     | 1.21.3             | ✅ ok      | **Build target**. PacketEvents 2.6.0 soporta. |
| 1.22+      | -                  | ❓ futuro  | Probar cuando salga; el plugin debería seguir funcionando si Bukkit API mantiene compat. |

## Soft dependencies (opcionales)

| Plugin            | Versión recomendada | Si está | Si no está |
|-------------------|---------------------|---------|------------|
| **PacketEvents**  | 2.6.0+              | Activa **17 checks packet-based** (Pack 47) + **20+ checks round 2** (Pack 48-A). | Anti-cheat sigue con `AnticheatListener` Bukkit-based (checks de Pack 44/45/46). |
| **LuckyPerms**    | 5.4+                | Los permisos del plugin (`argus.admin`, `argus.alerts`, `argus.ac.bypass`) se evalúan con tu permission system. | Cae a OP por defecto. |
| **ViaVersion**    | 5.x+                | Compatible — PacketEvents normaliza packets entre versiones de cliente. | Plugin acepta solo clientes ≤ version del server. |
| **ProtocolLib**   | -                   | No usado.| - |

### PacketEvents

`pom.xml` declara `com.github.retrooper:packetevents-spigot:2.6.0` como `provided`.
El plugin detecta si PacketEvents está cargado (vía
`PacketEventsBootstrap.detect()`) y, en caso positivo, registra el listener
de packets. Si no está, ArgusMC sigue funcionando con AnticheatListener Bukkit.

### ViaVersion

PacketEvents 2.x integra con ViaVersion: los packets de clientes en versiones
"viejas" se traducen al protocolo del server antes de llegar a nuestros
listeners. **No requiere código especial en ArgusMC** — los wrappers de
PacketEvents devuelven los campos ya normalizados.

Verificado en stack:
- Server Paper 1.21.3
- ViaVersion 5.3.0
- Cliente 1.8.9 → packets `PlayerPosition` / `InteractEntity` llegan
  correctamente y los checks de reach/aim funcionan.

## Proxy (BungeeCord / Velocity)

ArgusMC corre en cada **backend Spigot/Paper**, no en el proxy. Para que las
IPs reales lleguen al plugin, configura el proxy correctamente:

### BungeeCord

`spigot.yml` del backend:
```yaml
settings:
  bungeecord: true
```

`config.yml` de BungeeCord:
```yaml
ip_forward: true
```

ArgusMC usa `Player#getAddress()` para logs internos. Si BungeeCord está
configurado con `ip_forward`, esta dirección es la IP real del jugador.

### Velocity

`paper-global.yml`:
```yaml
proxies:
  velocity:
    enabled: true
    online-mode: true
    secret: '<tu secret>'
```

Velocity con `player-info-forwarding-mode: modern` envía la IP real automáticamente.

### Detección automática

Desde round 2, el plugin loguea al `onEnable` si detecta config de proxy:

```
[Argus] Proxy detection: BungeeCord=true | Velocity=false
```

Esto se hace via `Bukkit.spigot().getConfig().getBoolean("settings.bungeecord")`
y la presencia del archivo `paper-global.yml`. Es solo informativo — no cambia
el comportamiento del anti-cheat.

## Java

| Java version | Status |
|--------------|--------|
| 11           | ❌ no soportado (paper-api requiere 17+). |
| 17           | ✅ ok (1.17 – 1.20.4). |
| 21           | ✅ recomendado (1.20.5+ y 1.21.x). |

El plugin compila con `--release 21` (`pom.xml` lo declara). Para correr en un
server con Java 17, recompilar bajando `<java.version>17</java.version>` y
ajustar paper-api a una versión que soporte Java 17.

## Resumen para owners

- Server moderno (Paper 1.20+, Java 21, PacketEvents 2.6, LuckyPerms): **todo el plugin activo**.
- Server vanilla (Spigot 1.16+, Java 17): **anti-cheat reducido** sin packet-based, pero funcional.
- Server arcaico (Spigot 1.8 / Java 11): **no soportado**, recompilación necesaria.
