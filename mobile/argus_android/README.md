# Argus Android (APK) — Pack 25 MVP

Versión móvil del scanner anti-cheat Argus para **Minecraft Bedrock Edition**
y **Minecraft Java vía PojavLauncher / Boardwalk**. Comparte el contrato API
con el backend Argus (los mismos `POST /api/scans` y
`POST /api/scans/<id>/results` que usan los scanners Windows y Linux).

> Versión: **1.6.49-android1**
> Min SDK: 26 (Android 8.0)
> Target SDK: 34 (Android 14)
> Lenguaje: Kotlin · UI: Jetpack Compose

---

## Estado actual (Pack 25)

| # | Item del plan                                              | Estado |
|---|------------------------------------------------------------|--------|
| 1 | Refactor a paquete Android nativo (Gradle Kotlin)          | ✅ DONE |
| 2 | Aislar imports Windows/Linux                               | ✅ DONE |
| 3 | Equivalente Android de papelera (carpetas .recycle / Trash)| 🟡 PARTIAL — MediaStore IS_TRASHED queda Pack 26 |
| 4 | UsageStatsManager (apps lanzadas)                          | ⬜ TODO Pack 26 |
| 5 | FileObserver runtime (item USN)                            | ⬜ TODO Pack 26 |
| 6 | Detección de apps sospechosas (blacklist Bedrock+Java)     | ✅ DONE |
| 7 | Foreground app + overlays (SYSTEM_ALERT_WINDOW)            | ⬜ TODO Pack 26 |
| 8 | Soporte launchers MC móvil (Bedrock, Pojav, Boardwalk…)    | ✅ DONE |
| 9 | Captura de screenshot (MediaProjection)                    | ⬜ TODO Pack 26 |
| 10| Detección de root / Magisk / LSPosed / KernelSU            | ✅ DONE |
| 11| Game Guardian + memory editors                             | ✅ DONE |
| 12| Empaquetado APK universal sideload (zipalign + apksigner)  | 🟡 PARTIAL — proyecto build-ready, falta GH Actions |
| 13| Endpoint `/descargar/android` + tab UI con QR              | ✅ DONE (web_app) |
| 14| Política de permisos minimum-necessary                     | ✅ DONE |
| 15| Documentación + filtros honestos móvil                     | ✅ DONE |

**Pack 25 cubre 8/15 ítems explícitamente, 2 PARTIAL.** Pack 26 atacará los
que requieren más superficie de UI (UsageStats consent, MediaProjection,
overlays, FileObserver runtime).

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
| Prefetch / Amcache             | ✅ | ❌ | 🟡 UsageStatsManager (Pack 26) |
| USN Journal histórico          | ✅ | ❌ | ❌ (FileObserver runtime-only) |
| Procesos en memoria            | ✅ (WMI + ETW) | ✅ (/proc/maps) | 🟡 sandbox post-API 24 |
| Ventanas abiertas              | ✅ EnumWindows | ✅ wmctrl/Wayland | 🟡 UsageStats foreground |
| Screenshot multi-display       | ✅ ImageGrab | ✅ grim/scrot/spectacle | 🟡 MediaProjection (Pack 26) |
| Detección de root              | n/a | n/a | ✅ |
| Verificación de firma del APK  | ✅ Authenticode | ✅ rpm/dpkg | ✅ PackageManager |
| Memory editors (Game Guardian) | n/a | n/a | ✅ |
| Cheat clients oficiales        | ✅ desktop | ✅ desktop | ✅ Bedrock + Java móvil |

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
            ├── MainActivity.kt
            ├── ui/
            │   └── ScanScreen.kt          # Compose UI: 4 fases
            ├── core/
            │   ├── BackendClient.kt       # HTTP al backend Argus
            │   ├── HackTerms.kt           # Blacklists Bedrock + Java móvil
            │   ├── LegitMods.kt           # Whitelist mods legítimos
            │   ├── ScanOrchestrator.kt    # Coordina los 5 scanners
            │   └── ScanResult.kt          # Modelos + smartHackMatch
            └── scanners/
                ├── PackageScanner.kt      # #6 + #11 (cheat apps + memhack)
                ├── LauncherScanner.kt     # #8 (Bedrock/Pojav/Boardwalk)
                ├── FileScanner.kt         # #3 + #5 parcial
                ├── RootScanner.kt         # #10
                └── MemoryEditorScanner.kt # #11 (GG binarios + scripts)
```

---

## Roadmap Pack 26+ (próximas iteraciones)

- **#4 UsageStatsManager**: pantalla de consent + listado de apps lanzadas.
- **#5 FileObserver**: watch en runtime de carpetas Mojang/Pojav durante
  el scan window.
- **#7 Overlays activos**: cruzar foreground app con `SYSTEM_ALERT_WINDOW`
  para detectar ESP/wallhack overlay durante sesión de Minecraft.
- **#9 MediaProjection**: screenshot del dispositivo con consent dialog.
- **#12 GH Actions**: matrix CI con build automatizado y release nightly.
- **Anti-FP móvil**: integrar Bayesian-lite con tokens NEG `adaway/viper4android`
  vs POS `killaura/horion/gameguardian` (item #15).

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
