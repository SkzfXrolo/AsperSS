"""ai_maintenance.py — Pack 37: housekeeping automático del sistema IA.

Ejecuta una serie de operaciones de mantenimiento que mantienen el
sistema saludable sin requerir cron job (puede ser disparado manualmente
desde panel admin o por trigger externo):

  1. Decay de learned_hack_patterns:
       Patterns sin hit en >30 días: decay_score *= 0.95
       Patterns sin hit en >90 días: decay_score *= 0.80
       Si decay_score < 0.20 → confidence se asume insuficiente y el
       pattern queda inactivo de facto (get_active_patterns lo filtra).

  2. Decay de learned_patterns (legitimate_path):
       Patterns sin learned_from_count++ en >120 días Y is_active=TRUE:
       desactivar (mantener fila para auditoría).

  3. Recompute de trust_score para todos los staff:
       Por si quedó stale (e.g. después de un import masivo).

  4. Decay de company_fp_cooldown:
       Counters resetean a 0 si last_event_at > 24h (ya hace
       _maybe_decay automático, pero corremos un sweep general).

  5. Sugerencias de índices DB:
       Inspecciona el plan de queries comunes y emite recomendaciones.
       NO crea índices (decisión humana). Solo lista.

  6. Top sancionables por empresa:
       Ranking de minecraft_username con más verdicts hack en últimos
       N días (90 default). Útil para que el staff vea reincidentes.

Diseño:
  * Función `run_maintenance(cursor, dry_run=False)` ejecuta todos
    los pasos y devuelve un report dict.
  * Cada paso aislado en función propia para que se puedan correr
    individuales si se prefiere.
  * dry_run=True solo cuenta qué SE HARÍA sin tocar BD.
"""

from __future__ import annotations

from typing import Optional


def _ph(cursor) -> str:
    try:
        mod = cursor.connection.__class__.__module__.lower()
        if 'sqlite' in mod:
            return '?'
    except Exception:
        pass
    return '%s'


def _rg(row, idx: int, key: str):
    if row is None:
        return None
    if hasattr(row, 'get'):
        v = row.get(key)
        return v if v is not None else (row.get(idx) if isinstance(row, dict) else None)
    try:
        return row[idx]
    except Exception:
        return None


def decay_learned_hack_patterns(cursor, dry_run: bool = False) -> dict:
    """Decay de patterns sin hits recientes.
    Devuelve {decayed_30d, decayed_90d, deactivated_below_threshold}.
    """
    out = {'decayed_30d': 0, 'decayed_90d': 0, 'deactivated': 0}
    try:
        # Postgres syntax
        try:
            if not dry_run:
                cursor.execute(
                    "UPDATE learned_hack_patterns SET decay_score = decay_score * 0.95 "
                    "WHERE COALESCE(last_hit_at, learned_at) < CURRENT_TIMESTAMP - INTERVAL '30 days' "
                    "AND COALESCE(last_hit_at, learned_at) >= CURRENT_TIMESTAMP - INTERVAL '90 days' "
                    "AND decay_score > 0.20"
                )
                out['decayed_30d'] = cursor.rowcount or 0
                cursor.execute(
                    "UPDATE learned_hack_patterns SET decay_score = decay_score * 0.80 "
                    "WHERE COALESCE(last_hit_at, learned_at) < CURRENT_TIMESTAMP - INTERVAL '90 days' "
                    "AND decay_score > 0.20"
                )
                out['decayed_90d'] = cursor.rowcount or 0
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM learned_hack_patterns "
                    "WHERE COALESCE(last_hit_at, learned_at) < CURRENT_TIMESTAMP - INTERVAL '30 days' "
                    "AND COALESCE(last_hit_at, learned_at) >= CURRENT_TIMESTAMP - INTERVAL '90 days' "
                    "AND decay_score > 0.20"
                )
                out['decayed_30d'] = int(_rg(cursor.fetchone(), 0, 'count') or 0)
                cursor.execute(
                    "SELECT COUNT(*) FROM learned_hack_patterns "
                    "WHERE COALESCE(last_hit_at, learned_at) < CURRENT_TIMESTAMP - INTERVAL '90 days' "
                    "AND decay_score > 0.20"
                )
                out['decayed_90d'] = int(_rg(cursor.fetchone(), 0, 'count') or 0)
        except Exception:
            # SQLite fallback
            if not dry_run:
                cursor.execute(
                    "UPDATE learned_hack_patterns SET decay_score = decay_score * 0.95 "
                    "WHERE COALESCE(last_hit_at, learned_at) < datetime('now', '-30 days') "
                    "AND COALESCE(last_hit_at, learned_at) >= datetime('now', '-90 days') "
                    "AND decay_score > 0.20"
                )
                cursor.execute(
                    "UPDATE learned_hack_patterns SET decay_score = decay_score * 0.80 "
                    "WHERE COALESCE(last_hit_at, learned_at) < datetime('now', '-90 days') "
                    "AND decay_score > 0.20"
                )
        # Marca como deactivated los que cayeron debajo de threshold
        if not dry_run:
            cursor.execute(
                "UPDATE learned_hack_patterns SET decay_score = 0.0 "
                "WHERE decay_score > 0.0 AND decay_score < 0.20"
            )
            out['deactivated'] = cursor.rowcount or 0
    except Exception as e:
        print(f'[ai_maintenance.decay_hack] {e}')
    return out


def deactivate_stale_legit_patterns(cursor, dry_run: bool = False) -> dict:
    """Desactiva learned_patterns legítimos que no han hecho match en
    >120 días. Solo desactiva (no borra) para auditoría.
    """
    out = {'deactivated': 0}
    try:
        try:
            if not dry_run:
                cursor.execute(
                    "UPDATE learned_patterns SET is_active = FALSE "
                    "WHERE is_active = TRUE "
                    "AND last_updated_at < CURRENT_TIMESTAMP - INTERVAL '120 days' "
                    "AND learned_from_count <= 2"
                )
                out['deactivated'] = cursor.rowcount or 0
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM learned_patterns "
                    "WHERE is_active = TRUE "
                    "AND last_updated_at < CURRENT_TIMESTAMP - INTERVAL '120 days' "
                    "AND learned_from_count <= 2"
                )
                out['deactivated'] = int(_rg(cursor.fetchone(), 0, 'count') or 0)
        except Exception:
            if not dry_run:
                cursor.execute(
                    "UPDATE learned_patterns SET is_active = FALSE "
                    "WHERE is_active = 1 "
                    "AND last_updated_at < datetime('now', '-120 days') "
                    "AND learned_from_count <= 2"
                )
    except Exception as e:
        print(f'[ai_maintenance.legit_decay] {e}')
    return out


def recompute_all_trust_scores(cursor, dry_run: bool = False) -> dict:
    """Recompute trust_score para todos los staff_trust según las
    columnas current. Útil después de un bulk-import o si quedó stale.
    """
    out = {'updated': 0}
    try:
        try:
            if not dry_run:
                cursor.execute(
                    "UPDATE staff_trust SET trust_score = "
                    "100.0 * (1 + agreements + 2 * confirmed_correct) / "
                    "((1 + agreements + 2 * confirmed_correct) + "
                    " (1 + disagreements + 2 * confirmed_wrong))"
                )
                out['updated'] = cursor.rowcount or 0
            else:
                cursor.execute("SELECT COUNT(*) FROM staff_trust")
                out['updated'] = int(_rg(cursor.fetchone(), 0, 'count') or 0)
        except Exception as e:
            print(f'[ai_maintenance.recompute_trust] {e}')
    except Exception as e:
        print(f'[ai_maintenance.recompute_trust outer] {e}')
    return out


def cleanup_company_cooldowns(cursor, dry_run: bool = False) -> dict:
    """Resetea cooldowns con last_event_at >24h."""
    out = {'reset': 0}
    try:
        try:
            if not dry_run:
                cursor.execute(
                    "UPDATE company_fp_cooldown SET "
                    "fp_count_24h = 0, overturn_count_24h = 0, threshold_bump = 0 "
                    "WHERE last_event_at < CURRENT_TIMESTAMP - INTERVAL '24 hours' "
                    "AND (fp_count_24h > 0 OR overturn_count_24h > 0)"
                )
                out['reset'] = cursor.rowcount or 0
            else:
                cursor.execute(
                    "SELECT COUNT(*) FROM company_fp_cooldown "
                    "WHERE last_event_at < CURRENT_TIMESTAMP - INTERVAL '24 hours' "
                    "AND (fp_count_24h > 0 OR overturn_count_24h > 0)"
                )
                out['reset'] = int(_rg(cursor.fetchone(), 0, 'count') or 0)
        except Exception:
            if not dry_run:
                cursor.execute(
                    "UPDATE company_fp_cooldown SET "
                    "fp_count_24h = 0, overturn_count_24h = 0, threshold_bump = 0 "
                    "WHERE last_event_at < datetime('now', '-24 hours') "
                    "AND (fp_count_24h > 0 OR overturn_count_24h > 0)"
                )
    except Exception as e:
        print(f'[ai_maintenance.cooldown_cleanup] {e}')
    return out


def suggest_db_indexes(cursor) -> list:
    """Sugiere índices DB que probablemente ayudarían en queries comunes
    de Argus. NO crea los índices automáticamente — es decisión humana.

    Retorna lista de {table, columns, sql_create, reason}.
    """
    suggestions = [
        {
            'table':       'scans',
            'columns':     'minecraft_username (lower)',
            'sql_create':  'CREATE INDEX IF NOT EXISTS idx_scans_mc_username_lower ON scans (LOWER(minecraft_username))',
            'reason':      'Player timeline + risk profile + related-scans hacen LOWER(minecraft_username) match.',
        },
        {
            'table':       'scans',
            'columns':     'machine_id',
            'sql_create':  'CREATE INDEX IF NOT EXISTS idx_scans_machine_id ON scans (machine_id)',
            'reason':      'Prior consensus (Pack 32 F#55) y related-scans filtran por machine_id.',
        },
        {
            'table':       'scans',
            'columns':     'verdict_at',
            'sql_create':  'CREATE INDEX IF NOT EXISTS idx_scans_verdict_at ON scans (verdict_at) WHERE verdict_at IS NOT NULL',
            'reason':      'AI Quality metrics filtran por verdict_at >= NOW() - INTERVAL.',
        },
        {
            'table':       'scans',
            'columns':     'company_id, started_at',
            'sql_create':  'CREATE INDEX IF NOT EXISTS idx_scans_company_started ON scans (company_id, started_at DESC)',
            'reason':      'Listado paginado por empresa con orden temporal.',
        },
        {
            'table':       'scan_results',
            'columns':     'scan_id, alert_level',
            'sql_create':  'CREATE INDEX IF NOT EXISTS idx_scan_results_scan_alert ON scan_results (scan_id, alert_level)',
            'reason':      'Suggest learn-fp candidates filtra por alert_level dentro de scan.',
        },
        {
            'table':       'scan_results',
            'columns':     'file_hash',
            'sql_create':  'CREATE INDEX IF NOT EXISTS idx_scan_results_file_hash ON scan_results (file_hash) WHERE file_hash IS NOT NULL',
            'reason':      'Hash reputation system del ensemble lookups por hash.',
        },
        {
            'table':       'evidence_fingerprints',
            'columns':     'fingerprint',
            'sql_create':  'CREATE INDEX IF NOT EXISTS idx_evidence_fp ON evidence_fingerprints (LOWER(fingerprint))',
            'reason':      'Auto-learn check seen_count >= 50 para skip patterns.',
        },
        {
            'table':       'verdict_history',
            'columns':     'scan_id, changed_at',
            'sql_create':  'CREATE INDEX IF NOT EXISTS idx_verdict_history_scan ON verdict_history (scan_id, changed_at DESC)',
            'reason':      'Player timeline JOIN verdict_history por scan_id.',
        },
        {
            'table':       'staff_audit_log',
            'columns':     'user_id, action, timestamp',
            'sql_create':  'CREATE INDEX IF NOT EXISTS idx_audit_user_action ON staff_audit_log (user_id, action, timestamp DESC)',
            'reason':      'Staff activity heatmap + ranking de acciones.',
        },
        {
            'table':       'learned_hack_patterns',
            'columns':     'confidence DESC',
            'sql_create':  'CREATE INDEX IF NOT EXISTS idx_lhp_confidence ON learned_hack_patterns (confidence DESC) WHERE confidence > 0.30',
            'reason':      'get_active_patterns filtra confidence > 0.30.',
        },
    ]
    return suggestions


def get_top_repeat_offenders(cursor, company_id: Optional[int] = None,
                              since_days: int = 90, limit: int = 20) -> list:
    """Top jugadores con más verdicts 'hack' en los últimos N días.
    Útil para detectar reincidentes / ban candidates.
    """
    out = []
    try:
        ph = _ph(cursor)
        clauses = ["verdict = 'hack'", "minecraft_username IS NOT NULL"]
        params = []
        if company_id:
            clauses.append(f'company_id = {ph}')
            params.append(company_id)
        try:
            clauses.append(
                f"verdict_at >= CURRENT_TIMESTAMP - INTERVAL '{int(since_days)} days'"
            )
            where = ' AND '.join(clauses)
            cursor.execute(
                f'SELECT minecraft_username, COUNT(*) AS hacks, '
                f'  MAX(risk_score) AS max_risk, '
                f'  MAX(verdict_at) AS last_hack '
                f'FROM scans WHERE {where} '
                f'GROUP BY minecraft_username '
                f'HAVING COUNT(*) >= 2 '
                f'ORDER BY COUNT(*) DESC, MAX(verdict_at) DESC LIMIT {ph}',
                tuple(params + [limit])
            )
            rows = cursor.fetchall() or []
        except Exception:
            clauses[-1] = (
                f"verdict_at >= datetime('now', '-{int(since_days)} days')"
            )
            where = ' AND '.join(clauses)
            cursor.execute(
                f'SELECT minecraft_username, COUNT(*) AS hacks, '
                f'  MAX(risk_score) AS max_risk, '
                f'  MAX(verdict_at) AS last_hack '
                f'FROM scans WHERE {where} '
                f'GROUP BY minecraft_username '
                f'HAVING COUNT(*) >= 2 '
                f'ORDER BY COUNT(*) DESC, MAX(verdict_at) DESC LIMIT {ph}',
                tuple(params + [limit])
            )
            rows = cursor.fetchall() or []
        for r in rows:
            out.append({
                'minecraft_username': _rg(r, 0, 'minecraft_username'),
                'hacks':              int(_rg(r, 1, 'hacks') or 0),
                'max_risk':           int(_rg(r, 2, 'max_risk') or 0),
                'last_hack':          str(_rg(r, 3, 'last_hack') or ''),
            })
    except Exception as e:
        print(f'[ai_maintenance.top_offenders] {e}')
    return out


def run_maintenance(cursor, dry_run: bool = False) -> dict:
    """Ejecuta TODAS las operaciones de mantenimiento y devuelve report."""
    report = {
        'dry_run':        dry_run,
        'decay_hack':     decay_learned_hack_patterns(cursor, dry_run),
        'legit_decay':    deactivate_stale_legit_patterns(cursor, dry_run),
        'trust_recompute': recompute_all_trust_scores(cursor, dry_run),
        'cooldown_cleanup': cleanup_company_cooldowns(cursor, dry_run),
        'index_suggestions': suggest_db_indexes(cursor),
    }
    return report
