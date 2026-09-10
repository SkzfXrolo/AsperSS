# Argus Scanner 1.9.0 — DRAFT (release previsto: mes siguiente)

> **No bumpear versión en producción hasta el día del ship.**
> Hoy: terminar implementación. Release: sincronizar `SCANNER_VERSION` /
> `_ARGUS_VERSION` / `CURRENT_SCANNER_VERSION` + rebuild `.exe` + push.

## Objetivo del upgrade

Más señal forense para staff, menos ruido FP, UI que prioriza decisión.

## Incluido (acumulado post-1.8)

### UI / decisión
- Top 5 hallazgos + resto colapsado (`results_display.py`).
- Panel: Por qué / Cuándo / Relacionados.
- Veredicto + integridad con peso alto (1.8).

### Detección P1
- Catálogo `bundle/signatures/catalog.json` (hot-reload) + `ghost_config_paths`.
- Ghost registry ampliado, Recycle Bin hack names, launchers Desktop/Downloads.
- Startup folder + HKCU Run con stems de hack.
- UserAssist / Jump Lists / ShimCache con `match_hack_stem` + timestamps ISO.
- Pipeline Fast: UserAssist + Jump Lists en fase `temp_recent`.
- **Pipeline wiring P1 (antes solo legacy):** javaagent / JDWP / Weave / bat-ps1,
  ghost configs, Bloody+perfiles, Arduino HID (VID), SteelSeries/iCUE + jitter,
  Logitech/Razer macros, AHK.
- JDWP: cmdline + LISTEN :5005 / `address=`.
- javaagent: allowlist APM (`is_legit_java_agent`).
- Oleada red/evasión/complementos: VPN TUN/TAP, hosts Mojang+AC sinkhole, DNS
  cache hack domains, injectors activos, temp JARs, Baritone/Litematica/OptiFine/Xray
  en Fast; browser downloads/history en Standard+; Defender exclusions en evasion.
- USN #23: carpetas ghost borradas (`usn_ghost_folder`) + correlación residual.
- Memory strings (JARs cargados) en **Standard** (antes solo Paranoid).
- FP P2: `min_confidence_pct` / `ARGUS_MIN_CONFIDENCE`, demote >180d sin forense,
  grupos multi-evidencia FORENSIC/GHOST ampliados.
- FP P2 #6–8/#13–14: Authenticode demote (trusted publisher + signed PF),
  tamaño JAR (drop <3KB / soft <50KB), whitelist procesos ampliada,
  correlación nombre+ruta, parent launcher legítimo; java parent en pipeline.
- P2 #15/#18–20/#25/#27: short-lived processes, JAR structure/repack,
  launcher roots ampliados, Badlion/Lunar informativo, score decay por
  timestamp forense, fase `deep_proc` (clipboard, startup, inetcache, tree…).
- Panel: badge COMBO + `combination_penalty` en API/extra.
- Veredicto: buckets ampliados + peso por combos multi-evidencia.
- ETA Fast/Standard ajustados; Fast usa deep_proc ligero.
- Fix crítico: pipeline llamaba `scan_prefetch_hack_executions` (inexistente) →
  ahora `scan_prefetch_hacks` + `scan_prefetch_execution_parser`.
- deep_proc: +CheatEngine, recycle, jitter, RWX/DLL Java, hooks, PS history,
  Discord settings, messaging downloads, crash reports, fingerprints, etc.
- Evasión: time-drift NTP; Fast: cmd history + remote access tools (AnyDesk/TV).
- Fix: `advanced_minecraft_process_analysis` reemplaza call inexistente
  `scan_minecraft_process_info`.
- deep_proc: +54 scanners que solo corrían en legacy (tareas programadas,
  COM hijack, firewall rules, Defender quarantine, MRU/typed paths, USB
  history, texture packs, crash dumps, shadow copy, mass-delete, etc.).
- Paranoid: Sysmon/4688/LOLBins/ASR/signed-tamper/UEFI.
- Fast: lock files MC + RunMRU + VAC + remote access.
- Veredicto: bucket `persistence` + tipos remote/RDP/LOLBins en integrity.
- YARA: reglas Meteor/Wurst/Rise, Raven/Myau/Drip, Mixin/attach.
- Combos: `remote_help+cheat_signal`, `sched_task+execution`.
- Recycle Bin: match SHA256 vs catálogo offline (`recycle_hash_match`).
- Catálogo firmas **1.8.5**: stems + ghost_config_paths ampliados.
- ETA actualizado: Fast~4.5 / Standard~15 / Paranoid~30 min.
- FP: Wireshark/x64dbg/ProcessHacker → `POCO_SOSPECHOSO` (no ban solo).
- Panel: badges HASH (recycle hash-match) + REMOTE (AnyDesk/RDP).
- `forensic_match` carga `stems_extra` del catálogo en runtime.
- Hosts: más AC domains + sitios de cheats; custom genérico (adblock) ya no
  escala a SOSPECHOSO.
- Firewall: stem de hack en regla → `firewall_rule_hack`; resto user-dir only.
- Discord resumen: flags REMOTE / HASH_PAPELERA / COMBO.
- Combos: `recycle_hash+execution`, `remote_help+cheat_signal`, `sched_task+execution`.
- Texture packs: ya no reporta packs NORMAL; stems `ore/transparent/highlight`
  fuera (menos FP); confidence 0–1.
- Defender Quarantine: omitir histórico sin hits 72h.
- FP filter: drop hallazgos `NORMAL`; stems catálogo 1.8.5 en real_hack_patterns.
- UI local + Discord: flags REMOTE / HASH_PAPELERA / COMBO.
- Panel risk score: `recycle_hash` / remote / scheduled_task / yara;
  XRAY confirmado y crash dump Java ya no son zero-risk.
- YARA pack: `ss_cleaners.yar` (wipe forense + JVM attach).
- Panel detalle: chips REMOTE / HASH_PAPELERA / COMBO bajo el risk score.
- Firewall: skip Discord/Steam/Spotify/Lunar en AppData; combo hosts+dns.
- Mass-delete: stems de hack en cluster + tipo `deleted_mass_event`;
  combo `mass_delete+forensic`.
- USB historial: solo si el friendly name tiene stem de hack.
- TypedPaths / MUICache / WordWheelQuery: `match_hack_stem` (menos FP
  por `hack`/`cheat`/`macro` sueltos).
- RecentDocs → Standard; Amcache unique (ruidoso) fuera del pipeline.
- PS history: solo LOLBin/evasion fuertes + stem; crash reports sin tokens ambiguos.
- Combo `ps_history+evasion`.
- Fingerprints: +ThunderHack/Doomsday/Myau/Drip/Weave/Tenacity/etc.
- Discord webhooks: busca también en configs Meteor/LB/Rise/Rusher/TH.
- Git repos Desktop: `match_hack_stem` + remotes de distro.
- Combo `crash+ghost`; IP forwarding más soft (0.28).
- secondary_filter: stems catálogo 1.8.5+.
- options.txt keybinds: también Lunar / Feather / Badlion.
- Configs hack: `.properties`/`.json`/`.toml` también en Meteor/LB/Lunar/Badlion.
- Prefetch: `scan_prefetch_referenced_files` (DLL/JAR referenciados en .pf).
- Cookies: Chrome/Edge/Brave + WinINET hosts de cheats.
- Amcache: +InventoryDriverBinary / InventoryDeviceContainer.
- LNK: detección XAML/UWP hijack + LOLBin en target (`lnk_xaml_hijack`).
- Catálogo firmas **1.8.6** (más stems).
- Combos: `cookie+distro_signal`, `prefetch_ref+injection`.
- Panel/Discord/UI local: flags COOKIE / PREF_REF / LNK_HIJACK.
- Recycle: $R sin permisos no tumba el scan; VSS Unicode-safe.
- SRUM: `match_hack_stem`; YARA ThunderHack/Doomsday/Weave + Aristois pack.
- Backlog staff: regenerado (HTML).
- Discord cache: nombres/strings de cheats en Cache/Local Storage.
- Single-instance mutex (anti race 2× scanner); `--allow-multi` escape.
- Pipeline: timeout por scanner (15s Standard / `ARGUS_SCANNER_TIMEOUT`).
- `scan_injected_threads` (start addr fuera de módulos).
- `scan_minecraft_accounts` (multi-cuenta launcher).
- DLL sideload: +Desktop/Downloads/.minecraft/.lunarclient.
- FP: whitelist por categoría launcher/mod-loader/perf/QoL.
- FP: demote fuerte archivos >180d; processes con fallback UAC/tasklist.
- `scan_av_interference` (Prefetch/Amcache/SRUM bloqueados).
- deep_proc light en paralelo (2–4 workers) + timeout/scanner.

### FP / evidencia
- Boundary match Prefetch/USN/BAM/Amcache; kill-chain 2-of-3.
- Enrichment + `filter_stats` local.
- `normalize_path` (backslash escapado JSON) + Lunar 3.x (`.lunarclient` / Moonsworth).

## Checklist ship (mes del upgrade)

1. Bump `source/config/version.py` + fallback `main.py` → `1.9.0`
2. Bump `web_app/app.py` `_ARGUS_VERSION` + `CURRENT_SCANNER_VERSION`
3. PyInstaller `ArgusScanner.spec`
4. Commit `dist/ArgusScanner.exe` + fuentes de versión
5. Verificar `/panel` + `/api/version`

## Fuera de este draft

Backlog mega (~1200 ítems) sigue en `staff_roadmap_presentacion.html` /
`Argus_backlog_planificacion.html` — no es scope del 1.9 completo.
