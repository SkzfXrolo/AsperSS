# Argus Scanner 1.8.0

Mega-update orientado a **decisión staff**: modos predecibles, veredicto + timeline, integridad de alto peso, PIN SS y YARA en JARs.

## Novedades principales

### ScanPipeline + modos
- **Fast SS** (~2–4 min): procesos, JARs/MC, Prefetch/BAM, Temp/Recent, integridad, veredicto.
- **Standard** (~6–12 min): Fast + USN/Amcache/ShimCache + pack forense (sin `ext_*` ruidosos).
- **Paranoid** (~15–25 min): Standard + memory strings + YARA Java + mouse + módulos `ext_*`.
- Selector en UI + `ARGUS_SCAN_MODE` / `scan_mode` en config. Legacy: `ARGUS_LEGACY_SCAN=1`.

### Veredicto staff
- `ss_verdict` con timeline real y peso mayor a hallazgos `INTEGRITY`.
- **VerdictCard** al finalizar (veredicto, risk, top razones, kill-chain, acción).
- Discord (`scan_report`) incluye el mismo bloque + timeline corta.

### Integridad
- Gaps Prefetch vs BAM, wipe de Recent, cleaners, PS bypass (base ampliada en `ss_integrity`).

### PIN de sesión SS
- PIN de 6 dígitos ligado al `scan_token` (TTL 2 h, store local).
- Login acepta token o PIN; botón **PIN SS** para staff.

### YARA / firmas offline
- Reglas MC/inject/bypass en `yara_rules/` cableadas en fase Paranoid.
- Hot-reload de `offline_lexicon.json` / `offline_hash_catalog.bin` desde `%LOCALAPPDATA%\ArgusScanner\signatures\` o `signatures\` junto al `.exe`.

### Arquitectura
- FP filters en `fp_filter.py`; fases en `scan_pipeline.py`.
- `extended_checks` cableados al pack (OFF por defecto salvo Paranoid).

## Post-1.8 — FP + evidencia staff

- Boundary match USN/BAM/Amcache (`forensic_match.py`); kill-chain 2-of-3 Prefetch/BAM/USN.
- Cap Downloads orphan en Fast/Standard; `filter_stats` en `%LOCALAPPDATA%\ArgusScanner\perf\`.
- Panel: `extra.explicacion` / `timestamp` / `related_*`; UI “Por qué / Cuándo / Relacionados”.
- Feedback FP del panel sigue alimentando `ai_false_positives` / cooldown paths; el scanner aplica `legitimate_patterns` + remote FP rules en el próximo scan con red.

## Versión
Sincronizar: `source/config/version.py`, fallback `main.py`, `_ARGUS_VERSION` + `CURRENT_SCANNER_VERSION` en `web_app/app.py`.
