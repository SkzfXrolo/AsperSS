-- ============================================================================
-- Argus Projects — Pack 48 / subagente H
-- cleanup-policy-pack48.sql
-- ----------------------------------------------------------------------------
-- Retention policy recomendada para las tablas que crecen sin techo.
--
-- ⚠️  NO ejecutar este script entero de una sola vez. Cada bloque
-- está pensado para ser revisado, validado y ejecutado por separado.
-- Idealmente se llama desde un cron job (ej. `pg_cron`) o desde
-- `ai_maintenance.run_maintenance()` extendido.
--
-- Política por tabla (días):
--   * ai_decisions_log      → 180 días (auditable; player profile preserva en ai_player_scores)
--   * plugin_violations     → 365 días (legal-required parcial; ver REVIEW)
--   * staff_audit_log       → 365 días (legal — chequear con owner)
--   * verdict_history       → preservar todo (no DELETE — máx ~100k rows en años)
--   * ban_history           → preservar todo (legal-required, NUNCA borrar)
--   * evidence_fingerprints → 540 días sin hit
--   * ai_feedback           → preservar todo (training data sagrada)
--   * ai_auto_labels        → 90 días (regenerables por pipelines)
--   * auto_labels (ml)      → 180 días
--   * scan_results          → cascade desde scans, pero NO borramos scans
--                              salvo OLD scans sin verdict + sin staff_feedback (180d)
--   * scans                 → no borrar (cliente puede pedir reanálisis)
--   * scan_notes            → no borrar
--   * download_links        → DELETE expires_at < NOW() - 30d
--   * push_subscriptions    → DELETE último ping >180d (no tracked aún; PENDING)
--   * discord_queue         → DELETE processed_at < NOW() - 14d (sólo processed)
--   * ai_training_history   → preservar todo (auditoría ML)
--   * staff_trust           → recompute, no DELETE
--   * company_fp_cooldown   → ya hay auto-decay 24h
--   * learned_hack_patterns → ya hay decay; opcional DELETE decay_score=0 + >365d
--   * statistics            → preservar (rows pequeños)
--   * app_meta/app_settings → preservar
--
-- ----------------------------------------------------------------------------
-- IMPORTANTE — batches:
-- Para tablas grandes (>1M rows), un `DELETE WHERE created_at < ...` puede
-- bloquear horas. Usar el patrón LIMIT + loop:
--
--   DO $$
--   DECLARE deleted INT;
--   BEGIN
--     LOOP
--       DELETE FROM tabla WHERE id IN (
--         SELECT id FROM tabla WHERE created_at < ... LIMIT 10000
--       );
--       GET DIAGNOSTICS deleted = ROW_COUNT;
--       EXIT WHEN deleted = 0;
--       PERFORM pg_sleep(0.5);
--     END LOOP;
--   END $$;
--
-- O usar la herramienta `pg_repack` para mantener I/O bajo.
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 1 · ai_decisions_log (HIGH-VOL · 180d)
-- ────────────────────────────────────────────────────────────────────────────
-- Justificación: una decisión vigente vive en ai_player_scores. El log es
-- forense / training data, pero después de 180 días el player ya o tiene
-- decisión nueva o quedó dormido. ai_feedback referencia decision_id pero
-- conservamos las filas con feedback_attached.
--
-- BATCHED VARIANT (recomendada para prod):

DO $$
DECLARE deleted INT;
BEGIN
  LOOP
    DELETE FROM ai_decisions_log
    WHERE id IN (
      SELECT adl.id FROM ai_decisions_log adl
      LEFT JOIN ai_feedback af ON af.decision_id = adl.id
      WHERE adl.created_at < CURRENT_TIMESTAMP - INTERVAL '180 days'
        AND af.id IS NULL
      LIMIT 10000
    );
    GET DIAGNOSTICS deleted = ROW_COUNT;
    EXIT WHEN deleted = 0;
    RAISE NOTICE 'ai_decisions_log: deleted % rows', deleted;
    PERFORM pg_sleep(0.5);
  END LOOP;
END $$;

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 2 · plugin_violations (365d · REVIEW)
-- ────────────────────────────────────────────────────────────────────────────
-- [REVIEW · owner debe confirmar] Algunas jurisdicciones requieren conservar
-- evidencia de cheating ≥18 meses (compliance contractual con servidores).
-- Default seguro: 365 días.

DO $$
DECLARE deleted INT;
BEGIN
  LOOP
    DELETE FROM plugin_violations
    WHERE id IN (
      SELECT id FROM plugin_violations
      WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '365 days'
      LIMIT 10000
    );
    GET DIAGNOSTICS deleted = ROW_COUNT;
    EXIT WHEN deleted = 0;
    RAISE NOTICE 'plugin_violations: deleted % rows', deleted;
    PERFORM pg_sleep(0.5);
  END LOOP;
END $$;

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 3 · staff_audit_log (365d · REVIEW LEGAL)
-- ────────────────────────────────────────────────────────────────────────────
-- [REVIEW · staff_audit_log puede ser legal-required >2 años para auditoría
-- regulatoria si Argus se ofrece a clientes B2B con compliance. Confirmar con
-- el owner antes de aplicar.]

-- SUGERIDO (NO APLICAR sin confirmación):
-- DO $$ ... DELETE FROM staff_audit_log WHERE created_at < NOW() - INTERVAL '365 days' ...

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 4 · ai_auto_labels (90d · regenerable)
-- ────────────────────────────────────────────────────────────────────────────
-- Los auto-labels se regeneran cada vez que un pipeline corre. 90 días es
-- amplio; los training jobs sólo miran auto-labels recientes (<30d).

DO $$
DECLARE deleted INT;
BEGIN
  LOOP
    DELETE FROM ai_auto_labels
    WHERE id IN (
      SELECT id FROM ai_auto_labels
      WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days'
      LIMIT 10000
    );
    GET DIAGNOSTICS deleted = ROW_COUNT;
    EXIT WHEN deleted = 0;
    PERFORM pg_sleep(0.5);
  END LOOP;
END $$;

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 5 · auto_labels (180d)
-- ────────────────────────────────────────────────────────────────────────────
-- Tabla del ml_classifier original. Si una decisión humana invalida el
-- auto_verdict el código lo sobrescribe (UNIQUE scan_id), así que viejos
-- registros no aportan valor.

DELETE FROM auto_labels
WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '180 days';

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 6 · evidence_fingerprints (540d sin hit)
-- ────────────────────────────────────────────────────────────────────────────
-- Si un fingerprint no se ha vuelto a ver en 18 meses Y tampoco fue marcado
-- como hack ≥ 1 vez, lo borramos. Si fue hack al menos una vez lo dejamos
-- (signal valioso aunque no se reincida).

DELETE FROM evidence_fingerprints
WHERE last_seen_at < CURRENT_TIMESTAMP - INTERVAL '540 days'
  AND hack_count = 0;

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 7 · download_links (30d post-expiry)
-- ────────────────────────────────────────────────────────────────────────────
-- Tokens descargados o vencidos hace ≥30 días no aportan auditoría útil
-- (la tabla download_links es legalmente "registro de envío" no transacción
-- financiera).

DELETE FROM download_links
WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '30 days';

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 8 · discord_queue (14d post-processed)
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM discord_queue
WHERE processed_at IS NOT NULL
  AND processed_at < CURRENT_TIMESTAMP - INTERVAL '14 days';

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 9 · scans + scan_results "huérfanos" (180d sin verdict ni feedback)
-- ────────────────────────────────────────────────────────────────────────────
-- Scan que ningún staff revisó en 180d y no tiene staff_feedback, ni verdict,
-- ni notas. Probablemente fue pulled por mistake o el cliente lo abandonó.
-- scan_results se borra por CASCADE.

DO $$
DECLARE deleted INT;
BEGIN
  LOOP
    DELETE FROM scans
    WHERE id IN (
      SELECT s.id FROM scans s
      LEFT JOIN scan_results  sr ON sr.scan_id = s.id
      LEFT JOIN staff_feedback sf ON sf.scan_id = s.id
      LEFT JOIN scan_notes     sn ON sn.scan_id = s.id
      WHERE s.started_at < CURRENT_TIMESTAMP - INTERVAL '180 days'
        AND (s.verdict IS NULL OR s.verdict = 'pending')
        AND sf.id IS NULL
        AND sn.id IS NULL
      GROUP BY s.id
      HAVING COUNT(sr.id) = 0
      LIMIT 2000
    );
    GET DIAGNOSTICS deleted = ROW_COUNT;
    EXIT WHEN deleted = 0;
    RAISE NOTICE 'scans (huerfanos): deleted % rows', deleted;
    PERFORM pg_sleep(1);
  END LOOP;
END $$;

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 10 · learned_hack_patterns (365d · decay_score=0)
-- ────────────────────────────────────────────────────────────────────────────
-- ai_maintenance ya hace soft-disable (decay_score → 0.0). Hard-delete sólo
-- después de 365d con decay_score=0 (lo mantenemos por auditoría hasta entonces).

DELETE FROM learned_hack_patterns
WHERE decay_score = 0.0
  AND COALESCE(last_hit_at, learned_at) < CURRENT_TIMESTAMP - INTERVAL '365 days';

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 11 · registration_tokens (90d post-expiration)
-- ────────────────────────────────────────────────────────────────────────────

DELETE FROM registration_tokens
WHERE (is_used = TRUE OR expires_at < CURRENT_TIMESTAMP)
  AND COALESCE(used_at, expires_at, created_at) < CURRENT_TIMESTAMP - INTERVAL '90 days';

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 12 · scan_tokens (60d post-expiration sin scan asociado)
-- ────────────────────────────────────────────────────────────────────────────
-- Si un token tiene scans asociadas, NO borrar (cascade rompería el historial).

DELETE FROM scan_tokens
WHERE id IN (
  SELECT st.id FROM scan_tokens st
  LEFT JOIN scans s ON s.token_id = st.id
  WHERE st.expires_at < CURRENT_TIMESTAMP - INTERVAL '60 days'
    AND s.id IS NULL
);

-- ────────────────────────────────────────────────────────────────────────────
-- BLOQUE 13 · staff_feedback (PRESERVAR — sólo audit en lugar de DELETE)
-- ────────────────────────────────────────────────────────────────────────────
-- staff_feedback es la fuente de ground truth para el modelo ML.
-- NUNCA DELETE. Si el storage explota, archivar a otra DB (cold storage).

-- ────────────────────────────────────────────────────────────────────────────
-- POST-CLEANUP
-- ────────────────────────────────────────────────────────────────────────────
-- Recomendado correr después del cleanup:

VACUUM ANALYZE ai_decisions_log;
VACUUM ANALYZE plugin_violations;
VACUUM ANALYZE ai_auto_labels;
VACUUM ANALYZE auto_labels;
VACUUM ANALYZE evidence_fingerprints;
VACUUM ANALYZE download_links;
VACUUM ANALYZE discord_queue;
VACUUM ANALYZE scans;
VACUUM ANALYZE scan_results;
VACUUM ANALYZE learned_hack_patterns;

-- ============================================================================
-- TABLAS QUE REQUIEREN VALIDACIÓN HUMANA ANTES DE CUALQUIER DELETE
-- ============================================================================
--
-- [REVIEW] ban_history          — legal-required. NUNCA borrar.
-- [REVIEW] verdict_history      — auditoría inmutable. NUNCA borrar.
-- [REVIEW] staff_audit_log      — posible compliance B2B. Confirmar con owner.
-- [REVIEW] ai_training_history  — auditoría ML. Preservar mínimo 2 años.
-- [REVIEW] companies            — soft-delete (is_active=FALSE) en lugar de hard.
-- [REVIEW] users                — soft-delete (is_active=FALSE).
-- [REVIEW] hack_blacklist       — base de conocimiento; preservar.
-- [REVIEW] hack_hashes          — curado manualmente; preservar.
-- [REVIEW] mod_whitelist        — curado manualmente; preservar.
-- [REVIEW] ai_feedback          — ground truth ML. NUNCA borrar.
-- [REVIEW] ai_player_profiles   — vivo (UPSERT). No es append-only.
-- [REVIEW] ai_player_scores     — vivo (UPSERT). No es append-only.
-- ============================================================================

-- ============================================================================
-- VARIANTE SQLite
-- ============================================================================
-- SQLite no tiene DO $$ BEGIN ... END $$; loops. Para SQLite reemplazar por
-- DELETE simple con LIMIT (sólo SQLite 3.30+ con SQLITE_ENABLE_UPDATE_DELETE_LIMIT):
--
-- DELETE FROM ai_decisions_log
-- WHERE created_at < datetime('now', '-180 days');
--
-- Sin batching automático; para SQLite local el volumen suele ser bajo y un
-- DELETE full-scan es aceptable.
