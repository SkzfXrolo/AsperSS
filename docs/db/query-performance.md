# Argus Projects — Query performance audit (Pack 48-H Round 2)

> Alcance: `web_app/app.py` (~470 `execute()`). Módulos `web_app/argus_ai_*.py` **no contienen SQL** (Oracle/Trainer/Assistant son lógica pura o llaman helpers; la persistencia vive en `app.py` y en `auth.py` fuera de este audit).
> Metodología: grep estático + revisión de patrones JOIN / subquery / `DATE(started_at)`.
> Índices “propuestos”: `scripts/db/additional-indexes.sql` + `ai_maintenance.suggest_db_indexes`.

**Leyenda:** `~freq` = estimación relativa (alto / medio / bajo) según rutas HTTP calientes.

---

## Hallazgo transversal (argus_ai_*.py)

| Archivo | SQL en repo |
| --- | --- |
| `argus_ai_oracle.py` | **0** — `evaluate()` es pura; pesos vienen de `app.py` (`SELECT weights_json FROM ai_weights`). |
| `argus_ai_trainer.py` | **0** directo — entrena vía cursores pasados desde endpoints en `app.py`. |
| `argus_ai_assistant.py` | **0** directo. |
| `argus_ai_labeler.py` | **0** directo. |
| `argus_ai_features.py` | **0** directo. |

Por tanto las **30 queries** siguientes se ubican en `app.py` (y 1-2 referencias cruzadas a `information_schema`).

---

## Top 30 — tabla de auditoría

| # | Query / patrón | Ubicación ~L | ~freq | JOIN / complejidad | Índices actuales vs propuestos | N+1 | Recomendación | EXPLAIN en prod |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q01 | `SELECT issue_type, COUNT(*) … FROM scan_results sr JOIN scans s ON sr.scan_id=s.id WHERE s.verdict='hack' AND DATE(s.started_at)=?` | 507-515 | medio | 1 JOIN + **función en columna** `DATE(started_at)` | `idx_scan_id` en SR; scans: `idx_started_at` **no** cubre `DATE()` | No si batch diario | Particionar por mes o índice funcional `((started_at::date))`; evitar `DATE()` en WHERE | **Sí** |
| Q02 | `_daily_summary_job` mismo patrón con `DATE(started_at)` | 431-446 | bajo (cron 1/día) | scan_results + scans | igual Q01 | No | Materialized view diaria `scan_daily_stats` | **Sí** |
| Q03 | `SELECT COUNT(*) FROM scans` (health / stats) | 810, 1325 | alto | simple | `seq scan` en tablas grandes | No | `idx_p48h_scans_verdict_started` no aplica; COUNT(*) siempre seq — aceptable si <5M rows; sino **approx count** (`pg_class.reltuples`) para health | Opcional |
| Q04 | `SELECT COUNT(*) FROM scans WHERE status='running'` | 1326 | medio | simple | `idx_status` | No | OK | Opcional |
| Q05 | `SELECT COUNT(DISTINCT machine_id) FROM scans WHERE machine_id IS NOT NULL` | 1327 | medio | agregación + filter | `idx_scans_machine_id` (sugerido maintenance) | No | Aplicar `idx_scans_machine_id` si no existe | **Sí** |
| Q06 | `SELECT COUNT(*) FROM scan_results WHERE alert_level='CRITICAL'` | 1328 | medio | full table scan SR | `idx_alert_level` | No | Parcial `WHERE alert_level='CRITICAL'` si ratio bajo | **Sí** |
| Q07 | `SELECT COUNT(*) FROM scan_results` | 1329 | bajo | full scan | — | No | Solo dashboards; cache 60s Redis | Opcional |
| Q08 | `SELECT COUNT(*) FROM scan_tokens WHERE is_active=TRUE` | 1330 | medio | partial friendly | `idx_active(is_active, expires_at)` | No | OK | Opcional |
| Q09 | `SELECT COUNT(*) FROM scans WHERE verdict IN ('clean','hack',…)` | 1367-1371 | medio | filter | sin índice compuesto verdict | No | `idx_p48h_scans_verdict_started` | **Sí** |
| Q10 | `SELECT AVG(scan_duration) FROM scans WHERE scan_duration>0` | 1410 | bajo | agregado | — | No | OK para tamaño moderado | Opcional |
| Q11 | `SELECT 1 FROM scan_tokens WHERE short_code=?` (create token loop) | 2256, 2307 | alto | anti-collision | `idx_st_short_code` | **Sí** (hasta 20 round-trips) | Usar `INSERT … ON CONFLICT DO NOTHING RETURNING` | **Sí** |
| Q12 | `SELECT … FROM company_plugin_keys WHERE api_key=?` | 2820, 2953, 3810 | **muy alto** (cada `/api/plugin/*`) | simple | `idx_cpk_api_key` | No | OK; asegurar índice UNIQUE en api_key | **Sí** |
| Q13 | `SELECT COUNT(*) FROM plugin_violations WHERE …` (filtros dinámicos) | 3053 | alto | WHERE company_id / player / fechas | `idx_pv_company`, `idx_pv_created` | No | Revisar orden de columnas en índice compuesto según filtros más frecuentes; `idx_p48h_pv_company_check_level` | **Sí** |
| Q14 | `GROUP BY level` / `player_name` / `check_name` en `plugin_violations` | 3103-3117 | medio | agregación | índices simples | No | Considerar **rollup MV** horaria | **Sí** |
| Q15 | `SELECT weights_json FROM ai_weights WHERE company_id=?` | 3159-3165 | alto | simple | PK implícito por UNIQUE | No | **Cache app** 60s (ya documentado en oracle) — verificar implementación | Opcional |
| Q16 | `SELECT score, last_evaluated_at FROM ai_player_scores WHERE company_id=? AND player_uuid=?` | 3205 | alto | simple | `idx_aps_unique` | No | OK | **Sí** |
| Q17 | `SELECT COUNT(*) FROM scan_tokens WHERE company_id=?` (si existe columna) o variantes token | 3264 | medio | ver F-001 scans | — | No | Tras migración `scans.company_id`, índice compuesto | **Sí** |
| Q18 | `SELECT state_json FROM ai_model_state WHERE company_id=? AND model_kind=?` | 3384-3394 | medio | simple | `uq_aims_company_kind` | No | OK | Opcional |
| Q19 | `SELECT id, evidence_json FROM ai_decisions_log WHERE … ORDER BY created_at DESC LIMIT N` | 3602 | alto | ORDER + filter | `idx_adl_created` | No | `idx_p48h_adl_company_player_created` si filtra por player | **Sí** |
| Q20 | `SELECT player_uuid, feature_vector_json FROM ai_player_profiles WHERE company_id=?` (KNN batch) | 3627, 4332 | medio | puede traer **muchas filas** | `idx_app_company` | No | LIMIT + cursor pagination; **no** `SELECT *` sin cap | **Sí** |
| Q21 | `SELECT … FROM ai_feedback WHERE company_id=?` (full scan per company) | 3541 | medio-alto | filter company | `idx_af_company` | No | Añadir `ORDER BY created_at DESC LIMIT` siempre | **Sí** |
| Q22 | `SELECT … FROM ai_auto_labels WHERE company_id=? AND confidence>=?` | 3553 | medio | filter | `idx_aal_company` | No | índice `(company_id, confidence DESC)` | **Sí** |
| Q23 | `SELECT COUNT(*) FROM ai_decisions_log d WHERE … AND EXISTS (feedback) AND EXISTS (auto_labels)` | 4259-4263 | medio | **correlated subqueries** ×2 | `idx_af_decision`, `idx_aal_decision` | No | Reescribir a `LEFT JOIN … GROUP BY` o contador materializado | **Sí** |
| Q24 | `FROM ai_training_history WHERE company_id=? ORDER BY created_at DESC LIMIT` | 4285 | bajo | simple | `idx_ath_company` | No | OK | Opcional |
| Q25 | `FROM ai_decisions_log d WHERE … NOT EXISTS (feedback) NOT EXISTS (auto_labels)` | 4349-4352, 4507-4510 | alto | **anti-join** doble | índices en `decision_id` | No | Semi-join puede ser más barato que NOT EXISTS según stats | **Sí** |
| Q26 | `SELECT * FROM ai_player_profiles WHERE company_id=?` | 4391 | medio | **wide rows** (JSON grande) | `idx_app_company` | No | Seleccionar columnas necesarias; comprimir JSON | **Sí** |
| Q27 | `SELECT MAX(created_at) FROM plugin_violations WHERE company_id=? AND player_uuid=?` | 4642 | medio | aggregate + filter | `idx_p48h_pv_player_uuid_created` propuesto | No | Índice compuesto company+uuid+created | **Sí** |
| Q28 | `SELECT player_name, score FROM ai_player_scores WHERE company_id=? ORDER BY score DESC LIMIT` | 4848, 4907 | medio | sort | `idx_aps_score` | No | OK | **Sí** |
| Q29 | `SELECT action, COUNT(*) FROM ai_decisions_log WHERE company_id=? GROUP BY action` | 4875 | medio | hash aggregate | `idx_adl_action` | No | OK | **Sí** |
| Q30 | `SELECT player_name, score FROM ai_decisions_log WHERE company_id=? ORDER BY created_at DESC LIMIT` | 4950 | alto | order by created | `idx_adl_created` | No | Combinar con `idx_p48h_adl_company_player_created` | **Sí** |

### Queries legacy / riesgo (bonus, fuera del top 30 pero críticas)

| ID | Patrón | Línea ~ | Problema |
| --- | --- | --- | --- |
| X01 | `SELECT COUNT(*) FROM scans WHERE fecha > NOW()-1d` | 816 | Columna `fecha` **posiblemente inexistente** — typo legacy vs `started_at` |
| X02 | `FROM scan_verdicts` / `FROM empresas` | 822-828 | Tablas **no** en schema Pack 48 — dead code o otra BD |
| X03 | `SELECT * FROM scans ORDER BY id DESC LIMIT 3` | 5594 | Debug path; full row + seq scan |

---

## N+1 — resumen

| Ruta HTTP / función | Patrón N+1 | Mitigación |
| --- | --- | --- |
| `create_token` / `api_plugin_issue_token` | Loop `SELECT 1 FROM scan_tokens WHERE short_code=?` hasta 20× | `INSERT … ON CONFLICT` o advisory lock |
| Panel AI listados | Múltiples `SELECT` por player en loops Python (revisar callers de `get_classifier`) | Batch `WHERE player_uuid = ANY($1::text[])` |
| `get_scan` + nested results | A veces 1 query scan + 1 query results + 1 join tokens | Single query con JOIN o dataload |

---

## Lista prioritaria — **EXPLAIN ANALYZE** en producción

Ejecutar en ventana valle; sustituir literales por IDs reales anonimizados.

1. Q01 / Q02 — daily summary join + `DATE(started_at)`.
2. Q05 — `COUNT(DISTINCT machine_id)`.
3. Q11 — `short_code` lookup bajo carga.
4. Q12 — `company_plugin_keys` por `api_key` (hot path plugin).
5. Q13 — `plugin_violations` count con filtros típicos del panel.
6. Q19 — `ai_decisions_log` timeline por empresa.
7. Q20 — `ai_player_profiles` full company pull (KNN).
8. Q23 — double EXISTS en `ai_decisions_log`.
9. Q25 — double NOT EXISTS (unlabeled decisions).
10. Q27 — `MAX(created_at)` per player violations.
11. Q30 — `ai_decisions_log` recent by company.
12. Cualquier `LEFT JOIN scan_tokens` en `/api/scans/<id>` (grep `LEFT JOIN scan_tokens`).
13. `staff_audit_log` paginado (`/api/staff/audit-log`).
14. Listado `scans` por `company_id` **post-fix F-001** (cuando exista columna).
15. `push_subscriptions` full table select (`SELECT endpoint… FROM push_subscriptions`) — riesgo seq scan.

Los templates listos para copiar están en `scripts/db/explain-templates.sql`.

---

## Recomendaciones top (consolidado)

1. **Eliminar `DATE(column)` en WHERE** — usar rango `[ts::date, ts::date+1)` o columna generada `started_on DATE`.
2. **Corregir o borrar** queries X01–X02 si apuntan a tablas inexistentes (errores en logs / código muerto).
3. **Sustituir SELECT *** en tablas anchas (`ai_player_profiles`, `ai_decisions_log`) por proyecciones mínimas.
4. **Materializar** agregados del panel anti-cheat (`plugin_violations` por hora) si p95 > 100ms.
5. **Cache Redis** (60–300s) para `COUNT(*)` globales del health dashboard.
