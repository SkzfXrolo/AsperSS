# Argus Android (APK) — Pack 27: signed release + auto-updater

Versión móvil del scanner anti-cheat Argus para **Minecraft Bedrock Edition**
y **Minecraft Java vía PojavLauncher / Boardwalk**. Comparte el contrato API
con el backend Argus (los mismos `POST /api/scans` y
`POST /api/scans/<id>/results` que usan los scanners Windows y Linux).

> Versión: **1.6.49-android3**
> Min SDK: 26 (Android 8.0)
> Target SDK: 34 (Android 14)
> Lenguaje: Kotlin · UI: Jetpack Compose

## Novedades Pack 27

- **APK release firmado con keystore propio**. CI persiste un keystore
  RSA-2048 self-signed entre runs (publicado como release oculto
  `_keystore`). La firma es **estable**, así que builds nuevos se instalan
  como update sobre los previos sin pedir desinstalar.
- **Auto-updater in-app**. Al iniciar, la app consulta
  `/api/android-version?current=<commit>` y, si el backend reporta un
  build más reciente, muestra un banner "Hay versión nueva" con botón
  **Actualizar** que abre el APK firmado en el navegador para instalarlo.
- **`BuildConfig.ARGUS_BUILD_COMMIT` + `ARGUS_BUILD_TIMESTAMP`** inyectados
  desde CI; `versionCode` ahora viene del `github.run_number` (incrementa
  monotónicamente). Visible en el banner de update y enviable al backend
  como diagnóstico.

---

## Estado actual (Pack 26)

| # | Item del plan                                              | Estado |
|---|------------------------------------------------------------|--------|
| 1 | Refactor a paquete Android nativo (Gradle Kotlin)          | ✅ DONE |
| 2 | Aislar imports Windows/Linux                               | ✅ DONE |
| 3 | Equivalente Android de papelera (carpetas .recycle / Trash)| 🟡 PARTIAL — MediaStore IS_TRASHED queda Pack 27 |
| 4 | UsageStatsManager (apps lanzadas)                          | ✅ DONE (Pack 26) |
| 5 | FileObserver runtime (item USN)                            | ✅ DONE (Pack 26) |
| 6 | Detección de apps sospechosas (blacklist Bedrock+Java)     | ✅ DONE |
| 7 | Foreground app + overlays (SYSTEM_ALERT_WINDOW)            | ✅ DONE (Pack 26) |
| 8 | Soporte launchers MC móvil (Bedrock, Pojav, Boardwalk…)    | ✅ DONE |
| 9 | Captura de screenshot (MediaProjection)                    | ✅ DONE (Pack 26) |
| 10| Detección de root / Magisk / LSPosed / KernelSU            | ✅ DONE |
| 11| Game Guardian + memory editors                             | ✅ DONE |
| 12| Empaquetado APK universal sideload + GH Actions CI         | ✅ DONE (Pack 26) |
| 13| Endpoint `/descargar/android` + tab UI con QR              | ✅ DONE (web_app) |
| 14| Política de permisos minimum-necessary                     | ✅ DONE |
| 15| Documentación + filtros honestos móvil + Bayesian-lite     | ✅ DONE |

**Pack 26 cierra 13/15 ítems DONE + 1 PARTIAL.** Solo queda 1 item
parcialmente cubierto (#3 papelera vía MediaStore IS_TRASHED) que es
opcional por baja superficie de evidencia móvil.

### Nuevas capacidades en Pack 26

- **`UsageStatsScanner`**: detecta cheat clients/memory editors/root managers
  que fueron LANZADOS en los últimos 30 días con `queryUsageStats` +
  `queryEvents`. Reporta cantidad de launches, tiempo en foreground, último
  uso. Solo "instalado" → SOSPECHOSO, "instalado + lanzado" → CRITICAL.
  Bonus: histórico de sesiones de Minecraft Bedrock/Pojav como contexto
  INFO para el panel ("vino cheateando hace 10min vs hace 3 días").
- **`FileObserverScanner`**: monta watchers en runtime sobre las carpetas
  Mojang/Pojav/Download/AppPacks/Movies durante 12 segundos. Cualquier
  CREATE/MODIFY/DELETE/MOVE de un archivo con hack-term match durante el
  scan window se reporta como CRITICAL "actividad sospechosa durante el
  scan" (delata a alguien que intenta limpiar evidencia mientras corre el
  scanner).
- **`OverlayScanner`**: lista todas las apps con `OP_SYSTEM_ALERT_WINDOW`
  concedido. Si una app de la blacklist (Toolbox, Game Guardian) o con
  hack-term match en el label tiene overlay activo → reporta. Si encima
  Minecraft estuvo en foreground en la última hora → CRITICAL automático
  con confidence 0.97 (ESP/wallhack flotante en plena sesión). Whitelista
  apps benignas (Discord chathead, Twitch chat, Messenger, Maps).
- **`ScreenshotCapture`**: captura un frame del display con MediaProjection,
  comprime a PNG 70% y sube en base64 al backend en el mismo campo
  `screenshot` que Windows/Linux. Requiere consent dialog del SO en cada
  scan (no se puede skipear ni cachear). Toggle en la UI: el usuario puede
  desactivar el screenshot y el scan corre sin él.
- **`ScanForegroundService`**: notificación persistente "Argus está
  escaneando" mientras corre el flow. Tipo `dataSync|mediaProjection`
  combinado, requerido por Android 14+ para poder lanzar
  `MediaProjectionManager.getMediaProjection`. Garantiza que el scan no
  muere si el usuario manda Argus a background.
- **Bayesian-lite móvil**: `applyBayesianFilter()` en `ScanResult.kt`
  ajusta el confidence de cada hit por presencia de tokens NEG (`adaway`,
  `viper4android`, `lawnchair`, `tasker`, `kwgt`…) o POS (`killaura`,
  `horion`, `gameguardian`, `wallhack`…). Si el hit cae bajo umbrales se
  degrada CRITICAL→SOSPECHOSO o se descarta. Mismo patrón que F#27 desktop.
- **GH Actions CI**: `.github/workflows/android-build.yml` builda
  automáticamente `app-debug.apk` en cada push que toque
  `mobile/argus_android/**`. El APK queda como artifact descargable
  durante 30 días desde el run de Actions, sin necesidad de tener Android
  Studio instalado.

---

## Quickstart — compilar el APK

### Opción A: Android Studio (recomendado)

1. Abrir Android Studio Hedgehog (2023.1.1) o más nuevo.
2. **File ▸ Open** → seleccionar `mobile/argus_android/`.
3. Esperar el sync de Gradle (descarga AGP 8.2.2 + Kotlin 1.9.22 + Compose).
4. **Build ▸ Generate Signed Bundle / APK** → APK → debug o release.
5. El `.apk` queda en `app/build/outputs/apk/`.

### Opción B: Gradle CLI (sin Android Studio)

```bash
# Requisitos: JDK 17, Android SDK con platform-tools y build-tools 34.
export ANDROID_HOME=/path/to/android-sdk
cd mobile/argus_android

# Si no tenés Gradle wrapper aún, generalo desde tu Gradle 8.4+ local:
gradle wrapper --gradle-version 8.4

./gradlew assembleDebug          # Debug build (firmado con debug.keystore)
./gradlew assembleRelease        # Release (requiere release.keystore)
```

El APK se genera en:
- `app/build/outputs/apk/debug/app-debug.apk`
- `app/build/outputs/apk/release/app-release.apk`

### Opción C: GH Actions (próximamente)

Workflow en `.github/workflows/android.yml` se agregará en Pack 26 con
matrix de Android API 28/30/33/34. Cuando esté, cada push a `main` que
toque `mobile/argus_android/` publica un APK nightly en releases de GH.

---

## Distribución del APK

Una vez compilado el APK release:

```bash
# Copiar el APK a la carpeta servida por Flask para /descargar/android
cp app/build/outputs/apk/release/app-release.apk \
   ../../web_app/static/dist/argus-android.apk
```

El endpoint `/descargar/android` lo sirve con
`Content-Type: application/vnd.android.package-archive`. La página
`/descargar` muestra un tab "Android" con QR escaneable desde el móvil.

> **Importante**: NUNCA committear `release.keystore`, `*.jks` ni
> `keys.properties`. Ya están en `.gitignore`.

---

## Permisos requeridos (item #14)

Argus pide solo lo **minimum-necessary**. NO pedimos:
contactos · mic · cámara · ubicación · SMS · llamadas · Accessibility ·
REQUEST_INSTALL_PACKAGES · BIND_DEVICE_ADMIN.

| Permiso                      | Para qué                                        |
|------------------------------|-------------------------------------------------|
| `INTERNET`                   | Subir scan al backend Argus                     |
| `QUERY_ALL_PACKAGES`         | Item #6: blacklist de cheat clients             |
| `MANAGE_EXTERNAL_STORAGE`    | Items #3, #5, #8: revisar `/sdcard`             |
| `PACKAGE_USAGE_STATS`        | Items #4, #7: apps lanzadas + foreground        |
| `FOREGROUND_SERVICE` + media | Item #9: MediaProjection screenshot             |
| `POST_NOTIFICATIONS`         | Notif visible mientras el FGS scannea           |
| `WAKE_LOCK`                  | El scan no se duerme a mitad                    |

---

## Lo que la APK detecta

### Cheat clients Bedrock (el .apk ES el cheat)
Toolbox · Horion · Latite Mobile · Husky · Exodus · Prestige · Catalysm ·
Rebellion · FlareHCF · ProHvH · Moon Client · Zephyr HCF · Fracture · Phantom

### Memory editors / hack tools (item #11)
Game Guardian · GameCIH · MT Manager · Lucky Patcher · VirtualXposed ·
Parallel Space · CreditEdit · scripts `.lua/.gg/.gpb` en `/sdcard/Notes/GameGuardian/`

### Root / Xposed (item #10)
Magisk · KingoRoot · SuperSU · LSPosed · Xposed Installer · KernelSU ·
EdXposed · iRoot · Build.TAGS test-keys · `/system/xbin/su` y siblings

### Launchers Minecraft móvil cubiertos (item #8)
- `com.mojang.minecraftpe` · `minecraftedu` · `minecrafttrialpe` (Bedrock oficial)
- `net.kdt.pojavlaunch` · `pojavlauncher` · `com.kdt.pojavlauncher` (PojavLauncher Java)
- `com.boardwalk.boardwalk` · `org.boardwalk.merge` (Boardwalk Beta)
- `com.mcpemaster.mcpe` (MCPE Master)
- `net.zhuoweizhang.mcpelauncher` (BlockLauncher legacy)
- `com.tbox.box` · `com.toolbox.box` (Toolbox modo launcher)
- `org.jackhuang.hmcl` (HMCL Android) · `com.mclauncher.lithium`

Para cada launcher detectado:
- **Bedrock oficial**: verifica firma del APK contra Mojang AB.
  Si NO coincide → CRITICAL automático (APK pirata o con cheat inyectado).
- **PojavLauncher / Boardwalk**: lista `.jar` en `mods/` con SHA-256
  + match contra hack-terms (vape, liquid, wurst, sigma, impact, meteor,
  killaura, wallhack, etc.) excluyendo whitelist de mods legítimos
  (fabric, forge, optifine, sodium, lithium, jei, rei, geyser…).
- **Bedrock mod launchers**: revisa `.mcpack/.mcaddon` y scripts ModPE
  (`.js`) con tokens de hacks Bedrock.

### Archivos sospechosos (item #3 + #5 parcial)
Carpetas escaneadas:
- `/sdcard/Download/` (sideload)
- `/sdcard/.recycle`, `.recyclebin`, `RecycleBin`, `Trash`
- `/sdcard/.MIRecycleBin` (Mi File Manager)
- `/sdcard/.SE_Recycle` (Solid Explorer)
- `/sdcard/CXFileExplorer/Recycle`
- `/sdcard/AppPacks` (Toolbox addons)
- `/sdcard/games/com.mojang/` (Bedrock public)

Tipos detectados: `.apk`, `.jar`, `.zip`, `.dex`, `.mcpack`, `.mcaddon`,
`.mcworld`, `.js` (ModPE) con hack-term match (`smartHackMatch` con word
boundaries — mismo concepto que el scanner desktop).

---

## Diferencias honestas vs Windows / Linux

| Capacidad                      | Windows | Linux | Android |
|--------------------------------|:-:|:-:|:-:|
| Recycle Bin global             | ✅ ($Recycle.Bin) | ✅ (XDG Trash multi-mount) | 🟡 file-managers carpetas privadas |
| Prefetch / Amcache             | ✅ | ❌ | ✅ UsageStatsManager (Pack 26) |
| USN Journal histórico          | ✅ | ❌ | 🟡 FileObserver runtime-only (12s window, Pack 26) |
| Procesos en memoria            | ✅ (WMI + ETW) | ✅ (/proc/maps) | 🟡 sandbox post-API 24 |
| Ventanas abiertas              | ✅ EnumWindows | ✅ wmctrl/Wayland | ✅ UsageStats foreground (Pack 26) |
| Overlays activos (ESP móvil)   | n/a | n/a | ✅ AppOps OP_SYSTEM_ALERT_WINDOW (Pack 26) |
| Screenshot                     | ✅ ImageGrab | ✅ grim/scrot/spectacle | ✅ MediaProjection (Pack 26) |
| Detección de root              | n/a | n/a | ✅ |
| Verificación de firma del APK  | ✅ Authenticode | ✅ rpm/dpkg | ✅ PackageManager |
| Memory editors (Game Guardian) | n/a | n/a | ✅ |
| Cheat clients oficiales        | ✅ desktop | ✅ desktop | ✅ Bedrock + Java móvil |
| Bayesian-lite anti-FP          | ✅ F#27 | ✅ F#27 | ✅ móvil-specific (Pack 26) |

---

## Estructura del proyecto

```
mobile/argus_android/
├── build.gradle.kts            # Root (AGP 8.2.2 + Kotlin 1.9.22)
├── settings.gradle.kts
├── gradle.properties           # JVM args, Android flags
├── README.md                   # ESTE archivo
├── .gitignore
└── app/
    ├── build.gradle.kts        # App module (Compose, lifecycle, coroutines)
    ├── proguard-rules.pro
    └── src/main/
        ├── AndroidManifest.xml # Permisos minimum-necessary
        ├── res/                # strings, colors, themes, iconos vector
        └── java/com/argus/scanner/
            ├── ArgusApp.kt
            ├── MainActivity.kt                # Permisos + screenshot consent
            ├── ui/
            │   └── ScanScreen.kt              # Compose UI: 4 fases + toggle
            ├── service/
            │   └── ScanForegroundService.kt   # FGS dataSync|mediaProjection
            ├── core/
            │   ├── BackendClient.kt           # HTTP + screenshot upload
            │   ├── HackTerms.kt               # Blacklists Bedrock + Java móvil
            │   ├── LegitMods.kt               # Whitelist mods legítimos
            │   ├── ScanOrchestrator.kt        # Coordina los 9 scanners
            │   └── ScanResult.kt              # Modelos + smartHackMatch + Bayesian-lite
            └── scanners/
                ├── PackageScanner.kt          # #6 + #11 (cheat apps + memhack)
                ├── UsageStatsScanner.kt       # #4 (Prefetch móvil)
                ├── LauncherScanner.kt         # #8 (Bedrock/Pojav/Boardwalk)
                ├── FileScanner.kt             # #3 + #5 estático
                ├── FileObserverScanner.kt     # #5 runtime (12s)
                ├── OverlayScanner.kt          # #7 (overlay + cross-check MC)
                ├── RootScanner.kt             # #10
                ├── MemoryEditorScanner.kt     # #11 (GG binarios + scripts)
                └── ScreenshotCapture.kt       # #9 (MediaProjection + base64 PNG)
```

---

## Cómo conseguir el APK sin tener Android Studio

Tres caminos:

### Camino A — GitHub Actions (más rápido, sin instalar nada)

1. Andá a https://github.com/SkzfXrolo/AsperSS/actions/workflows/android-build.yml
2. Esperá a que termine el último run (verde, ~3 min después de cada push
   que toque `mobile/argus_android/**`).
3. Click en el run → bajá hasta **"Artifacts"** → descargá
   `argus-android-debug-<sha>.zip`.
4. Descomprimís → tenés `app-debug.apk` listo para sideload en cualquier
   Android 8.0+.

### Camino B — Compilarlo local (si querés modificar código)

```bash
cd mobile/argus_android
./gradlew assembleDebug              # 2-3 min en hardware decente
# APK en app/build/outputs/apk/debug/app-debug.apk
```

Requiere JDK 17 y Android SDK con build-tools 34.

### Camino C — Servirlo desde tu instancia Argus

Después de obtener el APK por A o B, copialo a:
```
web_app/static/dist/argus-android.apk
```

Y `https://tu-dominio/descargar/android` lo va a servir directamente con
QR escaneable desde el móvil.

---

## Instalación en el teléfono (sideload)

1. **Habilitar fuentes desconocidas**: Ajustes ▸ Apps ▸ Tu navegador o
   gestor de archivos ▸ "Permitir instalar apps desconocidas".
2. Abrir el `.apk` en el móvil → "Instalar".
3. Lanzar Argus Scanner.
4. **Onboarding**:
   - Otorgar "Acceso a archivos" (te lleva a Ajustes especiales).
   - Otorgar "Acceso al uso de apps" (te lleva a Ajustes ▸ Acceso especial).
5. **Iniciar scan**:
   - Pegar el token que te dio el staff.
   - Toggle "Adjuntar screenshot" (default ON — pide consent al SO).
   - Tap "Iniciar scan" → consent dialog de captura → scan corre ~30s.
   - Resultado en pantalla + subido al panel automáticamente.

> Si tenés el bot Discord, podés saltarte el paso del token usando un
> link `argus://scan?token=XXX` que abre la app con el token ya pegado.

---

## Roadmap Pack 27+ (próximas iteraciones, baja prioridad)

- **#3 MediaStore IS_TRASHED**: query del provider de media para listar
  archivos en papelera del SO (Android 11+). Complementa la cobertura
  de carpetas .recycle de file managers que ya está.
- **APK release firmada**: build pipeline con keystore en GitHub Secrets
  + auto-publish en GitHub Releases nightly. Hoy solo tenemos debug.
- **Play Store AAB**: opcional, requiere review de Google con descripción
  detallada de PACKAGE_USAGE_STATS y QUERY_ALL_PACKAGES (políticas
  estrictas de anti-cheat).
- **Modo --scan-self**: smoke test sin token contra mock backend.
- **Refresh dinámico de hack-terms**: descargar `/api/scanner-rules`
  desde el backend para que cuando aparezca un cheat client nuevo no
  haya que recompilar la APK.

---

## Smoke test sin token (`--scan-self`)

Pendiente Pack 26 — equivalente al modo `--scan-self` de Linux. Por
ahora cualquier token válido del staff arranca el flujo completo y
permite verificar que los 5 scanners corren sin crashes en el
dispositivo target.

---

## Soporte

- **Discord**: https://discord.gg/aMRJhbgNUZ — canal `#scanner-mobile`
- **Issues**: GitHub https://github.com/SkzfXrolo/AsperSS
- **Web**: https://asperss.onrender.com/descargar?plat=android

> "All-Seeing. Always Watching." — ahora también en tu bolsillo.
