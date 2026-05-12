# Argus Projects — Evolución del esquema por Pack

> Reconstruido leyendo los comentarios in-line del código (`# Pack N: ...`) más los commits relevantes. Fuente primaria: `web_app/app.py` (history) + `web_app/db_postgresql.py`.

Los Packs ≤30 quedaron fuera del alcance del Pack 48: la tabla base
(`scan_tokens`, `scans`, `scan_results`, `companies`, `users`, etc.) ya
existía antes y no hay registro embebido del Pack exacto en el que nació
cada columna. Para Packs ≥31 sí podemos reconstruir el delta.

---

## Línea de tiempo

```text
Pack ≤30  →  base "scanner" (scan_tokens, scans, scan_results, ban_history, ai_analyses,
                            staff_feedback, learned_patterns, learned_hashes,
                            ai_model_versions, app_versions, configurations,
                            statistics, companies, users, registration_tokens,
                            download_links)
Pack 31      [no DDL detectable]
Pack 32      staff_trust, company_fp_cooldown, company_settings
Pack 36      learned_hack_patterns                     (ai_autolearn.py)
Pack 37      ai_maintenance.py — no crea, decae
Pack 38-39   push_subscriptions, app_settings (vapid), evidence_fingerprints
Pack 40      scan_tokens.short_code
Pack 41      hotfix init order — no DDL nuevo
Pack 42      Aislamiento por company_id (parcial)      *(ver gap en findings)*
Pack 43      company_plugin_keys, plugin_violations,
             scan_tokens.+plugin_key_id, +minecraft_staff,
                          +minecraft_target, +source
Pack 44      ai_player_scores, ai_decisions_log, ai_weights
Pack 45      ai_feedback, ai_auto_labels, ai_model_state,
             ai_player_profiles, ai_training_history,
             auto_labels (ml_classifier helper)
Pack 46      sin DDL — Assistant usa tablas existentes
Pack 47      sin DDL — anti-cheat packet-based
Pack 48      (este pack) — backlog, no aplica DDL hasta validación H
```

---

## Detalle por Pack

### Pack 32 — Trust + cooldown + thresholds por empresa

**Tablas nuevas:**

- `staff_trust(user_id, agreements, disagreements, overturns_to_*, confirmed_*,
              trust_score, ...)` — Bayesian-smoothing del staff.
- `company_fp_cooldown(company_id, fp_count_24h, overturn_count_24h,
                       threshold_bump, ...)` — auto-cooldown si una empresa
                       hace muchos overturns.
- `company_settings(company_id PK, mode, threshold_critical,
                    threshold_suspicious, ...)` — modo tournament/normal/casual.

**Columnas añadidas:** ninguna externa.

**Riesgo de upgrade:** las 3 son CREATE IF NOT EXISTS y se crean lazy en el
primer access — no requieren migración explícita. Compatible con SQLite y PG
gracias al fallback try/except.

**Decisión cuestionable:** `company_settings` se inlinea con su DDL completo
**3 veces** en `app.py` (lines 6270, 6361, 13722). Si en el futuro se agrega
una columna habrá que cambiarla en los tres lugares — bug latente.

### Pack 36 — Auto-learning de hack patterns

**Tablas nuevas:**

- `learned_hack_patterns(pattern_kind, pattern_value UNIQUE, confidence,
                          decay_score, ...)` — patterns aprendidos cuando un
                          staff con trust>=65 cierra un scan como hack.

**Columnas añadidas:** ninguna.

**Riesgo de upgrade:** ninguno (CREATE IF NOT EXISTS lazy).

**Cleanup:** `ai_maintenance.decay_learned_hack_patterns()` aplica decay 0.95/0.80
y desactiva los <0.20 — sin DELETE, sólo soft-disable.

### Pack 38-39 — Web Push + VAPID + evidence

**Tablas nuevas:**

- `push_subscriptions(endpoint UNIQUE, p256dh, auth, user_id, created_at)` — creada
  lazy desde `push_subscribe`.
- `app_settings(key PK, value)` — singleton para guardar VAPID keys.
- `evidence_fingerprints(fingerprint PK, sample_*, seen_count, hack_count,
                         clean_count, sample_scan_id)` — patterns globales de evidencia.

**Riesgo de upgrade:** bajo. Tablas independientes que no afectan inserts/queries
existentes. `app_settings` solapa conceptualmente con `app_meta` y `configurations`
— no se eligió consolidar (deuda técnica menor).

### Pack 40 — short_code para tokens de scan

**Columna nueva:**

- `scan_tokens.short_code VARCHAR(8) UNIQUE` — código 6-char human-readable que
  reemplaza el URL token largo en la UX del staff.

**Riesgo de upgrade:** medio. La columna se agrega en `init_db_async()` (`app.py:309`)
con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS short_code VARCHAR(8) UNIQUE`. En
PG esto toma `AccessExclusiveLock` aunque la columna ya exista (no-op pero el
lock se toma igual). El comentario en `app.py:359` explica que esto causaba
deadlocks con SELECTs concurrentes que hacían `LEFT JOIN scan_tokens`.

**Mitigación implementada:** `init_db_async` ahora corre sólo en boot (no en
`@before_request`); más `SET LOCAL lock_timeout = '3s'` antes del ALTER. Ver
`_ensure_plugin_keys_schema()` (`app.py:2318`).

### Pack 41 — Hotfix init order

No agrega DDL — sólo mueve `threading.Thread(target=init_db_async).start()` al
final del módulo para evitar `NameError` antes de que las defs estén disponibles
(las migraciones rompían silenciosamente).

### Pack 42 — Aislamiento por company_id

**Endpoint nuevo:** `/aspers-sa/api/orphan-staff` para que SuperAdmin asigne
explícitamente staff huérfanos (`company_id IS NULL`) a una empresa concreta.

**Columnas añadidas:** ninguna por DDL. Pack 42 establece la **convención**
de que el aislamiento se hace via `users.company_id` y se propaga con `JOIN`.
El código de `_get_company_settings`, `_get_company_cooldown`, etc., todos
filtran por `company_id`.

**🟥 Gap crítico de Pack 42:** las tablas más volumétricas (`scans`,
`scan_results`) **no tienen `company_id`** y el filtrado se hace via JOIN con
`scan_tokens.created_by` → `users.username` → `users.company_id`. Pero hay
6 queries en `app.py:15733-15765` que asumen que `scans.company_id` existe
**directamente**. Esos SELECT silenciosamente devuelven 0 rows en PG porque
la columna no existe — esto es un **bug latente** (depende de si se pasa por
ese codepath; función `_company_summary`).

Detallado con SEV-HIGH en `findings-pack48.md`.

### Pack 43 — Anti-cheat plugin Minecraft

**Tablas nuevas:**

- `company_plugin_keys(company_id, api_key UNIQUE, label, is_active, daily_quota,
                       used_today, quota_reset_at, ...)` — API keys multi-tenant.
- `plugin_violations(plugin_key_id, company_id, player_uuid, player_name,
                     check_name, level, details, server_label, related_token_id,
                     created_at)` — log inmutable de violations del plugin.

**Columnas añadidas a `scan_tokens`:**

- `plugin_key_id INTEGER` — link al key que generó el token.
- `minecraft_staff VARCHAR(160)` — quien ejecutó `/ss`.
- `minecraft_target VARCHAR(160)` — el jugador investigado.
- `source VARCHAR(32) DEFAULT 'web'` — web | plugin.

**Riesgo de upgrade:** medio-alto. Los `ALTER TABLE` se ejecutan con
`SET LOCAL lock_timeout = '3s'`, pero si el cluster tiene gran tráfico al
boot pueden quedar pendientes y no aplicarse en ese ciclo. El código tolera
el fallo (try/except + print) y reintenta en el próximo boot. **Acción
recomendada**: en producción ejecutar manualmente cada ALTER fuera de horario.

### Pack 44 — Argus AI Oracle

**Tablas nuevas:**

- `ai_player_scores(company_id, player_uuid, score, confidence, last_action,
                    evaluations_count, ...)` — estado vigente per-player. UNIQUE(company_id, player_uuid).
- `ai_decisions_log(company_id, plugin_key_id, player_uuid, player_name,
                    score, confidence, action, reasoning, evidence_json,
                    triggered_by, created_at)` — log append-only. Alta cardinalidad.
- `ai_weights(company_id UNIQUE, weights_json, updated_by, updated_at)` — pesos
  del modelo configurables (company_id=0 → globales).

**Riesgo de upgrade:** bajo (todas nuevas).

**Volumen esperado:** `ai_decisions_log` crece linealmente con violaciones del
plugin. A 200 quota/día/key × N keys × 365d puede llegar a 100k-500k rows/año.
Sin retention. Ver `cleanup-policy-pack48.sql`.

### Pack 45 — ML híbrido (LogReg + KNN + Temporal + auto-labeling)

**Tablas nuevas:**

- `ai_feedback(company_id, decision_id, player_uuid, label, source,
               staff_username, ...)` — feedback explícito del staff sobre decisiones.
- `ai_auto_labels(company_id, decision_id, label, confidence, source, ...)` —
  pseudo-labels generados por los pipelines.
- `ai_model_state(company_id, model_kind, state_json, version, accuracy,
                  precision, recall, f1, ...)` — UNIQUE(company_id, model_kind).
- `ai_player_profiles(company_id, player_uuid, feature_vector_json,
                      last_label, ...)` — UNIQUE(company_id, player_uuid). Vectores KNN.
- `ai_training_history(company_id, model_kind, samples_used, epochs, loss,
                       accuracy, precision, recall, f1, duration_ms, ...)` — auditoría de retrains.

**Adicional:**

- `auto_labels(scan_id UNIQUE, auto_verdict, confidence, created_at)` — creada por
  `ml_classifier.py:541`. **No confundir con `ai_auto_labels`**. Esta vive en el
  classifier Python original (anterior a Pack 45). Solapa conceptualmente.

**Riesgo de upgrade:** bajo. Todas nuevas, idempotentes.

**Decisión cuestionable:** `auto_labels` y `ai_auto_labels` deberían unificarse.
Hoy una se usa por `ml_classifier.HackClassifier`, la otra por el ORACLE-pipeline
de Pack 45. La diferencia es que `auto_labels` se referencia por `scan_id` y la
otra por `decision_id` — usar ambas no es bug, pero el naming confunde.

### Pack 46 — Assistant

**Sin DDL nuevo.** El Assistant es un wrapper conversacional sobre `ai_player_scores`,
`plugin_violations`, `scans`, `verdict_history`. Sólo añade endpoints REST.

### Pack 47 — Anti-cheat packet-based (PacketEvents)

**Sin DDL nuevo.** Toda la lógica vive en el plugin Java. Los nuevos check names
(VClipCheck, StepCheck, etc.) se persisten en `plugin_violations.check_name`
sin necesidad de migración.

### Pack 48 — Backlog actual

**Aún sin DDL aplicado.** El backlog (`MEJORAS_PACK48.txt`) lista 720 mejoras
candidatas. Las que potencialmente requieren cambios DB:

- I#01: bootstrap dataset 5k+ → posible columna `samples_bootstrap` en
  `ai_training_history`.
- I#05: confusion matrix 4×4 → posible tabla `ai_confusion_matrix` o columna JSON
  en `ai_training_history`.
- I#08: cv_std → columna en `ai_training_history`.
- I#17: ROC/AUC → columna `auc REAL` en `ai_training_history`.
- I#34: online learning → no requiere DDL.

**Recomendación H:** consolidar las nuevas métricas en un único `metrics_json TEXT`
en `ai_training_history` (en lugar de N columnas dispersas) para evitar churn
de schema en cada Pack.

---

## Cambios potencialmente breaking (por orden de severidad)

1. **`scans.company_id` queryado sin existir** (Pack 42, SEV-HIGH). Ver `findings`.
2. **`scan_tokens.short_code` ALTER bloqueante** (Pack 40, SEV-MED). Mitigado con
   lock_timeout, pero todavía toma AccessExclusiveLock un instante.
3. **`scan_results` ALTER COLUMN TYPE TEXT** en `db_postgresql.py:152-154`. Cambia
   tipo de VARCHAR(255) → TEXT en cada boot — es no-op si ya era TEXT pero usa
   AccessExclusiveLock. Idempotente en la práctica pero quitar del path de boot.
4. **`download_links.created_by` cambio de FK INTEGER → VARCHAR(100)**
   (`db_postgresql.py:468`). Migración destructiva ejecutada en cada boot;
   protegida con try/except. Idempotente, pero quitar del path de boot.
5. **`users.avatar_url` ALTER** (`db_postgresql.py:463`). Igual que arriba —
   idempotente pero mantiene el lock al boot.

---

## Sugerencias de versionado futuro

Esta auditoría hace evidente que **no hay un sistema de migraciones formal**.
Cada deployment de Render re-ejecuta todos los `CREATE IF NOT EXISTS` /
`ALTER IF NOT EXISTS` al boot. Funciona, pero:

- No hay numeración de versiones del schema.
- No hay forma de "down-migrate" (rollback ordenado).
- La detección de cambios depende de leer 3 archivos Python diferentes.
- Los DDL embebidos en código Python son ilegibles para herramientas externas
  (Datagrip, DBeaver, dbml…).

**Recomendación H (para Pack 49+):** introducir `alembic` (o `yoyo-migrations` si
se quiere algo más ligero), generar la versión 1 a partir del esquema actual
con `pg_dump -s` + handwriting, y a partir de allí cada Pack agrega una
migración numerada.
