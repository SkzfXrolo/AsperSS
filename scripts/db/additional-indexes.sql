-- ============================================================================
-- Argus Projects — Pack 48 / subagente H
-- additional-indexes.sql
-- ----------------------------------------------------------------------------
-- Índices RECOMENDADOS adicionales (sobre los que ya crea el código).
-- NO duplica las 10 sugerencias que ya emite `ai_maintenance.suggest_db_indexes`
-- (éstas viven en web_app/ai_maintenance.py y se ejecutan a discreción
-- del admin). Ver `docs/db/schema-pack48.md` para el listado completo.
--
-- Dialecto base: PostgreSQL 14+.
-- Cada bloque incluye variante SQLite cuando difiera (BLOQUE_SQLITE).
--
-- Política:
--   * Todos con IF NOT EXISTS (idempotentes).
--   * Se prefiere CREATE INDEX CONCURRENTLY en PG para no bloquear la tabla,
--     pero CONCURRENTLY no se puede usar dentro de una transacción — por eso
--     en este script los CONCURRENTLY están comentados y se aplican
--     manualmente desde `migration-runbook.md`.
--   * Nombres con prefijo `idx_p48h_` para que sean identificables como Pack 48-H.
--
-- Aplicar en orden. Cada índice tiene comentario justificando la query
-- que optimiza.
-- ============================================================================

\timing on
SET statement_timeout = '5min';

-- ---------------------------------------------------------------------------
-- 1) scans — el caballo de batalla
-- ---------------------------------------------------------------------------

-- Listado del panel SuperAdmin (filtra verdict + orden temporal).
-- Query: SELECT * FROM scans WHERE verdict = ? ORDER BY started_at DESC LIMIT 50
CREATE INDEX IF NOT EXISTS idx_p48h_scans_verdict_started
    ON scans (verdict, started_at DESC)
    WHERE verdict IS NOT NULL;
-- SQLite:   sin WHERE parcial (SQLite soporta partial index pero conservador)
-- CREATE INDEX IF NOT EXISTS idx_p48h_scans_verdict_started ON scans (verdict, started_at DESC);

-- Player timeline (consulta por minecraft_username + orden temporal).
-- Query: SELECT * FROM scans WHERE LOWER(minecraft_username) = LOWER(?) ORDER BY started_at DESC
-- Nota: ai_maintenance ya sugiere idx_scans_mc_username_lower; éste es el
-- complemento con orden temporal.
CREATE INDEX IF NOT EXISTS idx_p48h_scans_mc_user_started
    ON scans (LOWER(minecraft_username), started_at DESC)
    WHERE minecraft_username IS NOT NULL;

-- Filtros por risk_score (panel de alta-prioridad).
-- Query: SELECT * FROM scans WHERE risk_score >= 70 ORDER BY started_at DESC
CREATE INDEX IF NOT EXISTS idx_p48h_scans_risk_high
    ON scans (started_at DESC)
    WHERE risk_score >= 70;

-- Búsqueda por scan_token (URL del staff).
-- Query: SELECT * FROM scans WHERE scan_token = ?
-- Ya existe idx_scan_token pero conviene unique para que el optimizer pick.
-- NO se crea UNIQUE acá porque puede haber tokens reutilizados en debug — sólo
-- B-tree no-unique. Si la app garantiza unicidad, promover a UNIQUE.

-- IP-based investigation (anti-fraud).
CREATE INDEX IF NOT EXISTS idx_p48h_scans_ip_started
    ON scans (ip_address, started_at DESC)
    WHERE ip_address IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2) scan_results — JOINs con scans + filtros
-- ---------------------------------------------------------------------------

-- feedback_status filter (panel de revisión de feedback).
-- Query: SELECT * FROM scan_results WHERE feedback_status IS NULL AND scan_id = ?
CREATE INDEX IF NOT EXISTS idx_p48h_scan_results_pending_feedback
    ON scan_results (scan_id)
    WHERE feedback_status IS NULL;

-- Búsqueda por hash (cloud lookup + feedback loop).
-- Ya existe idx_scan_results_file_hash en ai_maintenance.suggest. Sólo añade
-- combinada con alert_level para el panel "hashes sospechosos".
CREATE INDEX IF NOT EXISTS idx_p48h_scan_results_hash_alert
    ON scan_results (file_hash, alert_level)
    WHERE file_hash IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3) plugin_violations — alta cardinalidad, queries por jugador y check
-- ---------------------------------------------------------------------------

-- Player + temporal (Assistant le pregunta historial del player).
-- Query: SELECT * FROM plugin_violations WHERE player_uuid = ? ORDER BY created_at DESC LIMIT 100
CREATE INDEX IF NOT EXISTS idx_p48h_pv_player_uuid_created
    ON plugin_violations (player_uuid, created_at DESC)
    WHERE player_uuid IS NOT NULL;

-- Empresa + check_name + nivel (heatmap del panel anti-cheat).
-- Query: SELECT check_name, level, COUNT(*) FROM plugin_violations
--        WHERE company_id = ? AND created_at >= NOW() - INTERVAL '7 days'
--        GROUP BY check_name, level
CREATE INDEX IF NOT EXISTS idx_p48h_pv_company_check_level
    ON plugin_violations (company_id, check_name, level, created_at DESC);

-- ---------------------------------------------------------------------------
-- 4) ai_decisions_log — log volumétrico
-- ---------------------------------------------------------------------------

-- Empresa + player + temporal (perfil del jugador en Oracle).
-- Query: SELECT * FROM ai_decisions_log
--        WHERE company_id = ? AND player_uuid = ? ORDER BY created_at DESC LIMIT 20
CREATE INDEX IF NOT EXISTS idx_p48h_adl_company_player_created
    ON ai_decisions_log (company_id, player_uuid, created_at DESC)
    WHERE player_uuid IS NOT NULL;

-- Sólo acciones impactantes (descarta 'none').
-- Query: SELECT * FROM ai_decisions_log
--        WHERE action IN ('kicked','banned') AND created_at >= NOW() - INTERVAL '30 days'
CREATE INDEX IF NOT EXISTS idx_p48h_adl_action_critical
    ON ai_decisions_log (action, created_at DESC)
    WHERE action IN ('kicked', 'banned', 'ss_issued');

-- ---------------------------------------------------------------------------
-- 5) ai_feedback — agregaciones para training set
-- ---------------------------------------------------------------------------

-- Label + created_at (training pipeline pull).
-- Query: SELECT * FROM ai_feedback WHERE label IS NOT NULL ORDER BY created_at DESC LIMIT 5000
CREATE INDEX IF NOT EXISTS idx_p48h_af_label_created
    ON ai_feedback (label, created_at DESC);

-- Source filter (staff vs auto).
CREATE INDEX IF NOT EXISTS idx_p48h_af_source_created
    ON ai_feedback (source, created_at DESC);

-- ---------------------------------------------------------------------------
-- 6) ai_player_profiles — queries del KNN
-- ---------------------------------------------------------------------------

-- last_label filter (sólo perfiles labeled para KNN).
-- Query: SELECT feature_vector_json, last_label FROM ai_player_profiles
--        WHERE company_id = ? AND last_label IS NOT NULL ORDER BY last_updated_at DESC
CREATE INDEX IF NOT EXISTS idx_p48h_app_company_labeled
    ON ai_player_profiles (company_id, last_updated_at DESC)
    WHERE last_label IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 7) ai_training_history — drift detection
-- ---------------------------------------------------------------------------

-- model_kind + temporal (gráficos de evolución de métricas).
-- Query: SELECT accuracy, f1, created_at FROM ai_training_history
--        WHERE model_kind = ? ORDER BY created_at DESC LIMIT 50
CREATE INDEX IF NOT EXISTS idx_p48h_ath_model_created
    ON ai_training_history (model_kind, created_at DESC);

-- ---------------------------------------------------------------------------
-- 8) staff_audit_log — queries por usuario y tipo de acción
-- ---------------------------------------------------------------------------

-- ai_maintenance.suggest_db_indexes recomienda idx_audit_user_action
-- (user_id, action, timestamp DESC) — pero el nombre real de la columna es
-- created_at, NO timestamp (ver findings F-010). Versión correcta:
CREATE INDEX IF NOT EXISTS idx_p48h_audit_user_action_created
    ON staff_audit_log (user_id, action, created_at DESC);

-- Scan-scope timeline (qué acciones se hicieron sobre cierto scan).
CREATE INDEX IF NOT EXISTS idx_p48h_audit_scan_created
    ON staff_audit_log (scan_id, created_at DESC)
    WHERE scan_id IS NOT NULL;

-- Búsqueda por IP (forense).
CREATE INDEX IF NOT EXISTS idx_p48h_audit_ip_created
    ON staff_audit_log (ip_address, created_at DESC)
    WHERE ip_address IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 9) verdict_history — joins con scans en player timeline
-- ---------------------------------------------------------------------------

-- changed_by ranking (quién emite más verdicts).
CREATE INDEX IF NOT EXISTS idx_p48h_vh_changed_by
    ON verdict_history (changed_by, changed_at DESC);

-- verdict + temporal (filtro panel "últimos hacks confirmados").
CREATE INDEX IF NOT EXISTS idx_p48h_vh_verdict_changed
    ON verdict_history (verdict, changed_at DESC);

-- ---------------------------------------------------------------------------
-- 10) ban_history — búsquedas forenses
-- ---------------------------------------------------------------------------

-- IP-based ban search (ej. ban evasion).
CREATE INDEX IF NOT EXISTS idx_p48h_ban_ip_banned
    ON ban_history (ip_address, banned_at DESC)
    WHERE ip_address IS NOT NULL;

-- hack_type histograma.
CREATE INDEX IF NOT EXISTS idx_p48h_ban_hack_type_banned
    ON ban_history (hack_type, banned_at DESC)
    WHERE hack_type IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 11) download_links — expiración / cleanup
-- ---------------------------------------------------------------------------

-- Auto-cleanup query: SELECT * FROM download_links WHERE expires_at < NOW() AND is_active
-- Cubierta parcial por idx_active (is_active, expires_at).
-- Reforzamos con un index funcional para WHERE expires_at < NOW():
CREATE INDEX IF NOT EXISTS idx_p48h_dl_active_expired
    ON download_links (expires_at)
    WHERE is_active = TRUE;

-- ---------------------------------------------------------------------------
-- 12) discord_queue — ya tiene index parcial; añadir uno por event_type
-- ---------------------------------------------------------------------------

-- Query: SELECT * FROM discord_queue WHERE event_type = ? AND processed_at IS NULL
CREATE INDEX IF NOT EXISTS idx_p48h_dq_event_pending
    ON discord_queue (event_type, created_at)
    WHERE processed_at IS NULL;

-- ---------------------------------------------------------------------------
-- 13) registration_tokens — admin panel
-- ---------------------------------------------------------------------------

-- expires_at + is_used (panel "tokens activos").
CREATE INDEX IF NOT EXISTS idx_p48h_regtok_active_expires
    ON registration_tokens (expires_at)
    WHERE is_used = FALSE;

-- ---------------------------------------------------------------------------
-- 14) users — login búsquedas case-insensitive
-- ---------------------------------------------------------------------------

-- Login (case-insensitive). El código usa LOWER() en algunos paths.
CREATE INDEX IF NOT EXISTS idx_p48h_users_username_lower
    ON users (LOWER(username));

-- Listado por empresa + activos.
CREATE INDEX IF NOT EXISTS idx_p48h_users_company_active
    ON users (company_id, is_active);

-- ---------------------------------------------------------------------------
-- 15) learned_hack_patterns — pareja con sugerencia de ai_maintenance
-- ---------------------------------------------------------------------------

-- pattern_kind + decay_score (filtro KNN pattern lookup).
CREATE INDEX IF NOT EXISTS idx_p48h_lhp_kind_decay
    ON learned_hack_patterns (pattern_kind, decay_score DESC)
    WHERE decay_score > 0.20;

-- ---------------------------------------------------------------------------
-- 16) hack_blacklist + hack_hashes consolidación
-- ---------------------------------------------------------------------------

-- times_confirmed DESC (top hashes confirmados).
CREATE INDEX IF NOT EXISTS idx_p48h_blacklist_top
    ON hack_blacklist (times_confirmed DESC);

-- ---------------------------------------------------------------------------
-- 17) evidence_fingerprints — joins por sample_scan_id
-- ---------------------------------------------------------------------------

-- sample_scan_id (forense: qué scan introdujo este fingerprint).
CREATE INDEX IF NOT EXISTS idx_p48h_evfp_scan_id
    ON evidence_fingerprints (sample_scan_id)
    WHERE sample_scan_id IS NOT NULL;

-- last_seen DESC (panel "patterns activos recientes").
CREATE INDEX IF NOT EXISTS idx_p48h_evfp_last_seen
    ON evidence_fingerprints (last_seen_at DESC);

-- ---------------------------------------------------------------------------
-- 18) scan_tokens — quotas y plugin-key joins
-- ---------------------------------------------------------------------------

-- Filter por plugin_key_id (Pack 43 — quién emitió este token).
CREATE INDEX IF NOT EXISTS idx_p48h_st_plugin_key
    ON scan_tokens (plugin_key_id, created_at DESC)
    WHERE plugin_key_id IS NOT NULL;

-- source = 'plugin' analytics.
CREATE INDEX IF NOT EXISTS idx_p48h_st_source
    ON scan_tokens (source, created_at DESC);

-- ---------------------------------------------------------------------------
-- 19) company_plugin_keys — quota_reset_at cron
-- ---------------------------------------------------------------------------

-- Daily quota reset job: SELECT * FROM company_plugin_keys WHERE quota_reset_at < CURRENT_DATE
CREATE INDEX IF NOT EXISTS idx_p48h_cpk_quota_reset
    ON company_plugin_keys (quota_reset_at)
    WHERE quota_reset_at IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 20) ai_player_scores — leaderboard por score
-- ---------------------------------------------------------------------------

-- Already idx_aps_score(company_id, score DESC) exists. Add last_action filter
-- for "players in escalation queue":
CREATE INDEX IF NOT EXISTS idx_p48h_aps_company_action
    ON ai_player_scores (company_id, last_action, last_evaluated_at DESC)
    WHERE last_action <> 'none';

-- ---------------------------------------------------------------------------
-- 21) staff_feedback — agrega por staff
-- ---------------------------------------------------------------------------

-- ranking de feedback por staff (verified_by).
CREATE INDEX IF NOT EXISTS idx_p48h_sf_verified_by_at
    ON staff_feedback (verified_by, verified_at DESC)
    WHERE verified_by IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 22) statistics — agregados diarios (Pack 38)
-- ---------------------------------------------------------------------------

-- Ya tiene idx_date; aseguramos DESC también.
CREATE INDEX IF NOT EXISTS idx_p48h_stats_date_desc
    ON statistics (date DESC);

-- ---------------------------------------------------------------------------
-- 23) ai_auto_labels — ranking por source + confidence
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_p48h_aal_source_conf
    ON ai_auto_labels (source, confidence DESC, created_at DESC);

-- ===========================================================================
-- VARIANTES SQLITE (las funcionales con LOWER se mantienen, las parciales
-- con WHERE son válidas también; SQLite 3.8+ soporta partial indexes).
-- Saltarse las que usan IS NOT NULL en SQLite si la versión es <3.8.
-- ===========================================================================

-- Las definiciones anteriores son TODAS compatibles con SQLite 3.8+, excepto:
-- * `WHERE col IN (...)` en partial — SQLite OK desde 3.8.
-- * `CREATE INDEX CONCURRENTLY` — sólo PG.
--
-- Para deployments locales SQLite ejecutar este mismo archivo: las sentencias
-- IF NOT EXISTS hacen no-op si ya existen.
--
-- Si el deployment SQLite es muy antiguo (<3.8), reemplazar partial indexes
-- por la versión completa (sin cláusula WHERE).

-- ============================================================================
-- POST-INSTALL — recomendaciones manuales
-- ============================================================================

-- Después de aplicar este script:
--   1. ANALYZE; (en PG: ANALYZE VERBOSE;) para refrescar las stats.
--   2. Verificar uso real con:
--        SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
--        FROM   pg_stat_user_indexes
--        WHERE  indexrelname LIKE 'idx_p48h_%'
--        ORDER  BY idx_scan DESC;
--   3. Después de 7-14 días, los índices con idx_scan = 0 pueden ser dropeados
--      (DROP INDEX CONCURRENTLY si PG14+).
