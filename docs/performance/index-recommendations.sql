-- Pack48-G: recomendaciones adicionales de índices (complementan ai_maintenance.suggest_db_indexes).
-- No incluyen duplicados directos de:
-- idx_scans_mc_username_lower, idx_scans_machine_id, idx_scans_verdict_at,
-- idx_scans_company_started, idx_scan_results_scan_alert, idx_scan_results_file_hash,
-- idx_evidence_fp, idx_verdict_history_scan, idx_audit_user_action, idx_lhp_confidence.

-- 1) /api/scans GET: filtros por date range + order reciente.
CREATE INDEX IF NOT EXISTS idx_scans_started_at_desc
ON scans (started_at DESC);
-- Mejora estimada: 2x-6x en listados por fecha sin company_id.

-- 2) /api/scans GET: filtro por verdict + sort.
CREATE INDEX IF NOT EXISTS idx_scans_verdict_started
ON scans (verdict, started_at DESC);
-- Mejora estimada: 1.8x-4x para vistas por estado (hack/clean/pending).

-- 3) /api/scans GET: filtro por token (JOIN scan_tokens).
CREATE INDEX IF NOT EXISTS idx_scans_token_id_started
ON scans (token_id, started_at DESC);
-- Mejora estimada: 1.5x-3x en joins frecuentes de staff/tokens.

-- 4) /api/scans filtros por score de riesgo.
CREATE INDEX IF NOT EXISTS idx_scans_risk_started
ON scans (risk_score DESC, started_at DESC);
-- Mejora estimada: 1.5x-3x en paneles de top riesgo.

-- 5) búsquedas por machine_name ILIKE.
CREATE INDEX IF NOT EXISTS idx_scans_machine_name_lower
ON scans (LOWER(machine_name));
-- Mejora estimada: 2x-8x en búsquedas textuales por máquina.

-- 6) búsquedas por IP.
CREATE INDEX IF NOT EXISTS idx_scans_ip_address
ON scans (ip_address);
-- Mejora estimada: 2x-5x en filtros forenses por IP.

-- 7) reporte de detalles por scan con orden de severidad.
CREATE INDEX IF NOT EXISTS idx_scan_results_scan_alert_issue
ON scan_results (scan_id, alert_level, issue_name);
-- Mejora estimada: 1.8x-4x en detalle de resultados por scan.

-- 8) joins staff_feedback por result_id / scan-level feedback.
CREATE INDEX IF NOT EXISTS idx_staff_feedback_result_id
ON staff_feedback (result_id);
-- Mejora estimada: 2x-10x en joins de feedback por resultado.

-- 9) historial de notas por scan.
CREATE INDEX IF NOT EXISTS idx_scan_notes_scan_created
ON scan_notes (scan_id, created_at DESC);
-- Mejora estimada: 3x-12x en carga de notas recientes por scan.

-- 10) tokens empresa: listados por created_by + fecha.
CREATE INDEX IF NOT EXISTS idx_scan_tokens_created_by_created_at
ON scan_tokens (created_by, created_at DESC);
-- Mejora estimada: 2x-6x en panel admin/company tokens.

-- 11) ai_decisions_log por company + created_at (timeline).
CREATE INDEX IF NOT EXISTS idx_adl_company_created
ON ai_decisions_log (company_id, created_at DESC);
-- Mejora estimada: 2x-7x en consultas de timeline/brief recientes.

-- 12) ai_decisions_log para acciones sancionables por confianza.
CREATE INDEX IF NOT EXISTS idx_adl_company_action_confidence
ON ai_decisions_log (company_id, action, confidence ASC, created_at DESC);
-- Mejora estimada: 2x-5x en "prioridad de revisión" y colas low-confidence.

-- 13) ai_decisions_log por player_uuid.
CREATE INDEX IF NOT EXISTS idx_adl_company_player_uuid_created
ON ai_decisions_log (company_id, player_uuid, created_at DESC);
-- Mejora estimada: 2x-8x en historial de jugador.

-- 14) ai_auto_labels por company + source + tiempo.
CREATE INDEX IF NOT EXISTS idx_aal_company_source_created
ON ai_auto_labels (company_id, source, created_at DESC);
-- Mejora estimada: 1.5x-4x en métricas de auto-label por origen.

-- 15) ai_feedback por company + created_at.
CREATE INDEX IF NOT EXISTS idx_af_company_created
ON ai_feedback (company_id, created_at DESC);
-- Mejora estimada: 1.5x-4x en analytics de feedback reciente.

-- 16) ai_player_scores top score por empresa (lecturas frecuentes).
CREATE INDEX IF NOT EXISTS idx_aps_company_last_eval
ON ai_player_scores (company_id, last_evaluated_at DESC);
-- Mejora estimada: 1.8x-5x en panel de scores recientes.

-- 17) plugin_violations: player_uuid timeline.
CREATE INDEX IF NOT EXISTS idx_pv_company_player_uuid_created
ON plugin_violations (company_id, player_uuid, created_at DESC);
-- Mejora estimada: 2x-7x en perfil de jugador del plugin.

-- 18) plugin_violations: dashboard por nivel + tiempo.
CREATE INDEX IF NOT EXISTS idx_pv_company_level_created
ON plugin_violations (company_id, level, created_at DESC);
-- Mejora estimada: 2x-6x en agregados por severidad.

-- 19) plugin_violations: top checks por empresa.
CREATE INDEX IF NOT EXISTS idx_pv_company_check_created
ON plugin_violations (company_id, check_name, created_at DESC);
-- Mejora estimada: 2x-6x en top check_name y reportes de tendencia.

-- 20) evidence_fingerprints por score para deduplicación priorizada.
CREATE INDEX IF NOT EXISTS idx_evidence_fingerprint_seen_count
ON evidence_fingerprints (seen_count DESC);
-- Mejora estimada: 1.3x-3x en heurísticas de consolidación por popularidad.
