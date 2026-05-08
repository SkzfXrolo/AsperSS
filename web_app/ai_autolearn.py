"""ai_autolearn.py — Pack 36: aprendizaje automático supervisado.

Cuando un staff con alto trust_score cierra un scan como 'hack', los
paths únicos (que NO aparecen frecuentemente en scans clean) se
guardan automáticamente en learned_hack_patterns con un boost. Esos
patterns son consultados en futuros scans para incrementar el risk
score si aparecen.

Idea clave: aprovechar la decisión humana confirmada como ground truth
para que la IA evolucione SOLA — sin retraining costoso del Random
Forest, solo agregando patterns confirmados.

Política:
  * Solo staff con trust_score >= 65 alimenta auto-learn (configurable).
  * Solo paths con seen_count <= 5 en evidence_fingerprints O paths con
    >=3 hack-verdict matches en últimos 30 días.
  * El path se guarda como pattern de hash si tiene file_hash, sino
    como path-fragment normalizado.
  * Cada match en futuros scans suma confidence, hasta capping.
  * Decay: si un pattern se aprendió hace >180 días sin nuevos hits,
    su confidence baja gradualmente.

NO desplaza al staff: solo es señal extra que ENTRA en
_compute_ensemble_verdict (System 1 risk_score) o como modifier
multiplicativo del confidence en _calculate_risk_score.
"""

from __future__ import annotations

import time as _time
from typing import Optional


_AUTOLEARN_TTL = 180.0    # 3 min — patterns aprendidos cambian poco
_TRUST_MIN_FOR_LEARN = 65 # umbral mínimo de staff trust para alimentar

_patterns_cache: dict = {'data': None, 'ts': 0.0}


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


def ensure_autolearn_table(cursor) -> None:
    """Crea learned_hack_patterns si no existe (idempotente)."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS learned_hack_patterns (
            id              SERIAL PRIMARY KEY,
            pattern_kind    VARCHAR(20)  NOT NULL,
            pattern_value   VARCHAR(512) NOT NULL,
            confidence      REAL    DEFAULT 0.6,
            hit_count       INTEGER DEFAULT 0,
            confirmed_count INTEGER DEFAULT 1,
            learned_from_scan_id INTEGER,
            learned_by      INTEGER,
            learned_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_hit_at     TIMESTAMP,
            decay_score     REAL DEFAULT 1.0,
            UNIQUE(pattern_kind, pattern_value)
        )
    ''')


def _normalize_path(p: str) -> str:
    if not p:
        return ''
    p = str(p).replace('/', '\\').lower().strip()
    # Tomamos los últimos 2 segmentos (carpeta + archivo) como pattern
    parts = p.split('\\')
    if len(parts) >= 2:
        return '\\'.join(parts[-2:])[:250]
    return parts[-1][:250]


def auto_learn_from_hack_verdict(
    cursor,
    scan_id: int,
    staff_user_id: int,
    staff_trust_score: float,
    results: Optional[list] = None,
) -> dict:
    """Llamar cuando un staff cierra verdict='hack'.

    Si el staff tiene trust >= TRUST_MIN, extrae los paths únicos del
    scan (no comunes en scans clean) y los agrega a learned_hack_patterns.

    Retorna dict con stats: {learned: int, skipped_low_trust: bool,
                             scanned: int}.
    """
    out = {
        'learned':           0,
        'skipped_low_trust': False,
        'scanned':           0,
        'reason':            '',
    }
    if staff_trust_score is None or staff_trust_score < _TRUST_MIN_FOR_LEARN:
        out['skipped_low_trust'] = True
        out['reason'] = f'staff trust ({staff_trust_score}) < umbral ({_TRUST_MIN_FOR_LEARN})'
        return out

    try:
        ensure_autolearn_table(cursor)
        ph = _ph(cursor)

        # Si no nos pasaron results, los leemos del scan
        if results is None:
            cursor.execute(
                'SELECT issue_path, issue_name, file_hash, alert_level, '
                'confidence FROM scan_results '
                f'WHERE scan_id = {ph} '
                f"AND alert_level IN ('SOSPECHOSO', 'CRITICAL')",
                (scan_id,)
            )
            rows = cursor.fetchall() or []
            results = []
            for r in rows:
                results.append({
                    'issue_path':  _rg(r, 0, 'issue_path'),
                    'issue_name':  _rg(r, 1, 'issue_name'),
                    'file_hash':   _rg(r, 2, 'file_hash'),
                    'alert_level': _rg(r, 3, 'alert_level'),
                    'confidence':  _rg(r, 4, 'confidence'),
                })

        out['scanned'] = len(results)
        if not results:
            out['reason'] = 'sin results sospechosos'
            return out

        # Filter: solo CRITICAL/SOSPECHOSO con confidence >=0.55
        learned = 0
        for r in results:
            level = (r.get('alert_level') or '').upper()
            if level not in ('SOSPECHOSO', 'CRITICAL'):
                continue
            try:
                conf = float(r.get('confidence') or 0.0)
            except Exception:
                conf = 0.0
            if conf < 0.55 and level != 'CRITICAL':
                continue

            path = r.get('issue_path') or ''
            name = r.get('issue_name') or ''
            fhash = r.get('file_hash') or ''

            # Preferimos hash si existe (más específico). Sino, path
            # fragment normalizado.
            if fhash and len(fhash) >= 16:
                kind, value = 'hash', fhash[:128]
            else:
                norm = _normalize_path(path or name)
                if not norm or len(norm) < 6:
                    continue
                kind, value = 'path_fragment', norm

            # Verificar que NO sea un pattern muy común (false positive
            # bait). Si seen_count en evidence_fingerprints es alto,
            # skipemamos: probablemente sea legítimo.
            try:
                cursor.execute(
                    f'SELECT seen_count FROM evidence_fingerprints '
                    f'WHERE LOWER(fingerprint) = LOWER({ph}) LIMIT 1',
                    (value,)
                )
                row = cursor.fetchone()
                if row:
                    sc = int(_rg(row, 0, 'seen_count') or 0)
                    if sc >= 50:
                        # Demasiado común para ser hack-pattern útil.
                        continue
            except Exception:
                pass  # tabla puede no existir

            # UPSERT en learned_hack_patterns
            try:
                cursor.execute(
                    f'UPDATE learned_hack_patterns SET '
                    f'  confirmed_count = confirmed_count + 1, '
                    f'  confidence = LEAST(0.95, confidence + 0.05), '
                    f'  last_hit_at = CURRENT_TIMESTAMP, '
                    f'  decay_score = 1.0 '
                    f'WHERE pattern_kind = {ph} AND pattern_value = {ph}',
                    (kind, value)
                )
                cursor.execute(
                    f'SELECT id FROM learned_hack_patterns '
                    f'WHERE pattern_kind = {ph} AND pattern_value = {ph}',
                    (kind, value)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        f'INSERT INTO learned_hack_patterns '
                        f'  (pattern_kind, pattern_value, confidence, '
                        f'   confirmed_count, learned_from_scan_id, '
                        f'   learned_by, last_hit_at) '
                        f'VALUES ({ph}, {ph}, 0.65, 1, {ph}, {ph}, '
                        f'        CURRENT_TIMESTAMP)',
                        (kind, value, scan_id, staff_user_id)
                    )
                learned += 1
            except Exception as e_in:
                print(f'[autolearn.upsert] {e_in}')

        # Invalida cache de patterns
        _patterns_cache['ts'] = 0.0

        out['learned'] = learned
        out['reason']  = f'aprendido {learned} de {out["scanned"]}'
        return out
    except Exception as e:
        print(f'[autolearn.auto_learn] {e}')
        out['reason'] = f'error: {e}'
        return out


def get_active_patterns(cursor) -> dict:
    """Devuelve un dict con dos listas (hashes / path_fragments) de
    learned_hack_patterns activos, con confidence y decay aplicado.

    Cache 3min para uso en hot-path (cada scan lo consulta).
    """
    now = _time.time()
    cached = _patterns_cache.get('data')
    if cached and (now - _patterns_cache.get('ts', 0)) < _AUTOLEARN_TTL:
        return cached
    out = {'hashes': {}, 'path_fragments': {}}
    try:
        ensure_autolearn_table(cursor)
        cursor.execute(
            'SELECT pattern_kind, pattern_value, confidence, '
            'confirmed_count, decay_score '
            'FROM learned_hack_patterns '
            'WHERE confidence > 0.30 LIMIT 5000'
        )
        for r in cursor.fetchall() or []:
            kind = (_rg(r, 0, 'pattern_kind') or '').lower()
            val  = (_rg(r, 1, 'pattern_value') or '').lower()
            conf = float(_rg(r, 2, 'confidence') or 0.0)
            decay = float(_rg(r, 4, 'decay_score') or 1.0)
            effective = conf * decay
            if effective < 0.30:
                continue
            if kind == 'hash':
                out['hashes'][val] = effective
            elif kind == 'path_fragment':
                out['path_fragments'][val] = effective
        _patterns_cache['data'] = out
        _patterns_cache['ts']   = now
    except Exception as e:
        print(f'[autolearn.get_active] {e}')
    return out


def boost_results_with_patterns(cursor, results: list) -> int:
    """Recorre results y, si un path/hash matchea un pattern aprendido,
    inyecta un campo extra `_autolearn_boost` con el boost (0-1) para
    que _calculate_risk_score lo use. Retorna # de results boosteados.
    """
    if not results:
        return 0
    try:
        patterns = get_active_patterns(cursor)
        if not patterns['hashes'] and not patterns['path_fragments']:
            return 0
        boosted = 0
        for r in results:
            fhash = (r.get('file_hash') or '').lower()
            if fhash and fhash in patterns['hashes']:
                r['_autolearn_boost'] = patterns['hashes'][fhash]
                r['_autolearn_kind']  = 'hash'
                boosted += 1
                continue
            path = (r.get('issue_path') or r.get('ruta') or '').lower().replace('/', '\\')
            for frag, conf in patterns['path_fragments'].items():
                if frag and frag in path:
                    r['_autolearn_boost'] = conf
                    r['_autolearn_kind']  = 'path'
                    r['_autolearn_match'] = frag
                    boosted += 1
                    break
        return boosted
    except Exception as e:
        print(f'[autolearn.boost] {e}')
        return 0


def get_player_risk_profile(cursor, username: str,
                            since_days: int = 365) -> dict:
    """Calcula perfil histórico de risk del jugador.

    Retorna:
      {risk_avg, risk_max, risk_min, risk_recent (last 5),
       trend ('rising'|'stable'|'falling'),
       regression_alert: bool, total_scans}
    """
    out = {
        'username':           username,
        'since_days':         since_days,
        'total_scans':        0,
        'risk_avg':           None,
        'risk_max':           None,
        'risk_min':           None,
        'risk_recent':        [],
        'trend':              'unknown',
        'regression_alert':   False,
        'regression_reason':  '',
    }
    try:
        ph = _ph(cursor)
        try:
            cursor.execute(
                'SELECT risk_score FROM scans '
                f"WHERE LOWER(minecraft_username) = LOWER({ph}) "
                f"  AND COALESCE(verdict_at, started_at, created_at) >= "
                f"      CURRENT_TIMESTAMP - INTERVAL '{int(since_days)} days' "
                f'ORDER BY COALESCE(started_at, created_at) DESC LIMIT 100',
                (username,)
            )
            rows = cursor.fetchall() or []
        except Exception:
            cursor.execute(
                'SELECT risk_score FROM scans '
                f"WHERE LOWER(minecraft_username) = LOWER({ph}) "
                f"  AND COALESCE(verdict_at, started_at, created_at) >= "
                f"      datetime('now', '-{int(since_days)} days') "
                f'ORDER BY COALESCE(started_at, created_at) DESC LIMIT 100',
                (username,)
            )
            rows = cursor.fetchall() or []

        scores = [int(_rg(r, 0, 'risk_score') or 0) for r in rows]
        scores = [s for s in scores if s is not None]
        if not scores:
            return out
        out['total_scans'] = len(scores)
        out['risk_avg'] = round(sum(scores) / len(scores), 1)
        out['risk_max'] = max(scores)
        out['risk_min'] = min(scores)
        out['risk_recent'] = scores[:5]  # ya están DESC
        # Trend: comparar promedio recent (last 5) vs older avg
        if len(scores) >= 6:
            recent_avg = sum(scores[:5]) / 5.0
            older_avg  = sum(scores[5:]) / max(1, len(scores) - 5)
            diff = recent_avg - older_avg
            if diff > 12:
                out['trend'] = 'rising'
            elif diff < -12:
                out['trend'] = 'falling'
            else:
                out['trend'] = 'stable'
            # Regression alert: si older era <30 (clean) y recent es >=70 (hack)
            if older_avg < 30 and recent_avg >= 70:
                out['regression_alert']  = True
                out['regression_reason'] = (
                    f'risk subió de {older_avg:.0f} (histórico) a '
                    f'{recent_avg:.0f} (recientes) — posible regresión a hacks.'
                )
        else:
            out['trend'] = 'insufficient_data'
        return out
    except Exception as e:
        print(f'[autolearn.player_risk] {e}')
        return out
