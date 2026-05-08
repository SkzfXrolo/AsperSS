"""ai_quality.py — Pack 35: métricas y auto-aprendizaje de la IA.

Este módulo le da a la IA (heurística + RF + Isolation Forest +
ensemble + ai_trust) capacidad de medir su propio rendimiento y
ajustarse:

  1. **AI Quality Dashboard** — métricas globales y por empresa:
       - precision/recall/f1 vs verdicts humanos confirmados
       - confusion matrix (predicted hack vs real hack)
       - drift score (qué tan lejos está el ensemble del humano)
       - top false positives recientes (paths que la IA flagea pero
         el staff descarta) → candidatos automáticos para learn-fp
       - top false negatives (paths que la IA descartó pero terminan
         siendo hack) → candidatos para subir confianza

  2. **Adaptive Thresholds** — sugiere ajuste de threshold_critical/
     suspicious por empresa basado en su histórico:
       - Si la empresa tiene precision <60% → sugiere subir threshold
         (para reducir FP; mejor perderse algo que sancionar mal).
       - Si la empresa tiene recall <60% → sugiere bajar threshold
         (la IA está siendo demasiado conservadora; alguien zafa).
       - Si está balanceado (60-80% ambos) → sin cambios sugeridos.

  3. **RF Retraining Trigger** — flag que indica cuándo conviene
     retrainear el modelo Random Forest:
       - Drift > 0.30 vs último train (verdicts humanos discrepan
         mucho con el modelo).
       - O > N nuevos verdicts confirmados desde último train
         (umbral configurable).
     No retrainea automáticamente — solo emite un flag que el admin
     ve en el dashboard.

  4. **Auto-suggest learn-fp**: identifica los 20 paths más reportados
     en scans con verdict=clean (es decir, la IA marcó algo que después
     todos los staff descartaron) y los sugiere para automation.

Diseño:
  * Cero deps nuevas — usa SQL agregado y lógica numérica.
  * Cache 5min para queries pesadas.
  * Compatible con Postgres y SQLite.
  * Si el módulo cae, el resto sigue funcionando.
"""

from __future__ import annotations

import time as _time
from typing import Optional

_QUALITY_TTL = 300.0    # 5 min — métricas globales
_SUGGEST_TTL = 600.0    # 10 min — sugerencias de learn-fp

_quality_cache: dict = {}    # {scope_key: (data, ts)}
_suggest_cache: dict = {}    # {scope_key: (data, ts)}


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
        if v is None and isinstance(row, dict):
            return row.get(idx)
        return v
    try:
        return row[idx]
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────
# 1. AI Quality Metrics
#
# Calcula precision/recall/f1 sobre los scans con verdict humano cerrado
# (clean / hack), comparando contra el ensemble verdict que tenía el
# scan en ese momento (extraído de ensemble_data JSON).
#
# Definiciones:
#   TP (True Positive)  = ensemble dice hack  AND humano dice hack
#   FP (False Positive) = ensemble dice hack  AND humano dice clean
#   FN (False Negative) = ensemble dice clean AND humano dice hack
#   TN (True Negative)  = ensemble dice clean AND humano dice clean
#
# Mapping ensemble → binario:
#   HACK_CONFIRMADO, MUY_SOSPECHOSO  → 'hack'
#   LIMPIO, POCO_SOSPECHOSO          → 'clean'
#   SOSPECHOSO                       → ambiguous (no cuenta)
# ──────────────────────────────────────────────────────────────────────
def get_quality_metrics(
    cursor,
    company_id: Optional[int] = None,
    since_days: int = 90,
) -> dict:
    """Devuelve precision/recall/f1/confusion del ensemble vs humano."""
    scope_key = f'q:{company_id or 0}:{since_days}'
    now = _time.time()
    cached = _quality_cache.get(scope_key)
    if cached and now - cached[1] < _QUALITY_TTL:
        return cached[0]

    out = {
        'tp': 0, 'fp': 0, 'fn': 0, 'tn': 0, 'ambiguous': 0,
        'precision': None, 'recall': None, 'f1': None, 'accuracy': None,
        'total_evaluated': 0, 'since_days': since_days,
        'company_id': company_id,
        'drift_score': None,
    }
    try:
        ph = _ph(cursor)
        params = []
        clauses = ["verdict IN ('clean', 'hack')",
                   "ensemble_data IS NOT NULL"]
        if company_id:
            clauses.append(f'company_id = {ph}')
            params.append(company_id)
        # Filtro temporal
        # PG: CURRENT_TIMESTAMP - INTERVAL '<N> days' / SQLite fallback
        try:
            clauses.append(
                "verdict_at >= CURRENT_TIMESTAMP - "
                f"INTERVAL '{int(since_days)} days'"
            )
            where = ' AND '.join(clauses)
            cursor.execute(
                f'SELECT verdict, ensemble_data FROM scans '
                f'WHERE {where} LIMIT 5000',
                tuple(params)
            )
            rows = cursor.fetchall() or []
        except Exception:
            clauses[-1] = (
                f"verdict_at >= datetime('now', '-{int(since_days)} days')"
            )
            where = ' AND '.join(clauses)
            cursor.execute(
                f'SELECT verdict, ensemble_data FROM scans '
                f'WHERE {where} LIMIT 5000',
                tuple(params)
            )
            rows = cursor.fetchall() or []

        import json as _json
        for r in rows:
            human = (_rg(r, 0, 'verdict') or '').lower()
            ed_raw = _rg(r, 1, 'ensemble_data')
            if not ed_raw:
                continue
            try:
                ed = _json.loads(ed_raw) if isinstance(ed_raw, str) else ed_raw
            except Exception:
                continue
            ev = (ed or {}).get('verdict', '').upper()
            if ev in ('HACK_CONFIRMADO', 'MUY_SOSPECHOSO'):
                ens = 'hack'
            elif ev in ('LIMPIO', 'POCO_SOSPECHOSO'):
                ens = 'clean'
            else:
                out['ambiguous'] += 1
                continue
            if ens == 'hack' and human == 'hack':
                out['tp'] += 1
            elif ens == 'hack' and human == 'clean':
                out['fp'] += 1
            elif ens == 'clean' and human == 'hack':
                out['fn'] += 1
            elif ens == 'clean' and human == 'clean':
                out['tn'] += 1

        tp, fp, fn, tn = out['tp'], out['fp'], out['fn'], out['tn']
        total = tp + fp + fn + tn
        out['total_evaluated'] = total
        if total > 0:
            out['accuracy'] = round((tp + tn) / total, 3)
        if (tp + fp) > 0:
            out['precision'] = round(tp / (tp + fp), 3)
        if (tp + fn) > 0:
            out['recall']    = round(tp / (tp + fn), 3)
        if out['precision'] is not None and out['recall'] is not None:
            p, r = out['precision'], out['recall']
            if (p + r) > 0:
                out['f1'] = round(2 * p * r / (p + r), 3)
        # Drift = % desacuerdo / total evaluado
        if total > 0:
            out['drift_score'] = round((fp + fn) / total, 3)

    except Exception as e:
        print(f'[ai_quality.metrics] {e}')
    _quality_cache[scope_key] = (out, now)
    return out


# ──────────────────────────────────────────────────────────────────────
# 2. Adaptive Thresholds: sugerencia (NO mutación automática).
#
# Política:
#   precision <0.60  → suggest threshold_critical += 5 (más estricto
#                       para reducir FP; menos sanciones erróneas).
#   precision >0.85 y recall <0.60 → threshold_critical -= 5
#                       (la IA es muy estricta y se le escapan; bajar
#                       umbral para detectar más).
#   60% ≤ ambos ≤ 85% → mantener.
#
# La empresa ve la sugerencia en el dashboard y decide si aplicarla.
# ──────────────────────────────────────────────────────────────────────
def suggest_threshold_adjustment(metrics: dict) -> dict:
    """Devuelve {action: 'raise'|'lower'|'keep', delta: int, rationale: str}"""
    out = {'action': 'keep', 'delta': 0, 'rationale': '',
           'confidence': 'low'}
    p = metrics.get('precision')
    r = metrics.get('recall')
    n = metrics.get('total_evaluated', 0)
    if p is None or r is None or n < 30:
        out['rationale'] = 'Necesitas al menos 30 verdicts cerrados para sugerir un ajuste'
        return out
    out['confidence'] = 'high' if n >= 100 else 'medium'
    if p < 0.60:
        out['action']    = 'raise'
        out['delta']     = 5 if p >= 0.45 else 10
        out['rationale'] = (
            f'Precision baja ({p*100:.0f}%): la IA flagea hacks que el staff '
            f'descarta. Subir threshold reduce FPs.'
        )
    elif p > 0.85 and r < 0.60:
        out['action']    = 'lower'
        out['delta']     = -5
        out['rationale'] = (
            f'Recall bajo ({r*100:.0f}%) con alta precision ({p*100:.0f}%): '
            f'la IA es muy conservadora, se le escapan hacks reales. '
            f'Bajar threshold detecta más.'
        )
    else:
        out['action']    = 'keep'
        out['rationale'] = (
            f'Métricas balanceadas (P={p*100:.0f}% R={r*100:.0f}%). '
            f'Sin ajuste necesario.'
        )
    return out


# ──────────────────────────────────────────────────────────────────────
# 3. RF Retraining Trigger.
#
# Detecta cuándo conviene retrainear el Random Forest:
#   * drift_score > 0.30  → modelo desactualizado
#   * verdicts_since_last_train > 200 → suficiente data nueva
#   * última fecha de train > 30 días atrás
#
# NO retrainea solo (decisión humana). Solo emite el flag.
# ──────────────────────────────────────────────────────────────────────
def should_retrain_rf(metrics: dict, last_train_at: Optional[str] = None,
                      verdicts_since_train: int = 0) -> dict:
    out = {
        'should_retrain':       False,
        'reasons':              [],
        'urgency':              'low',  # low | medium | high
    }
    drift = metrics.get('drift_score')
    if drift is not None and drift > 0.30:
        out['should_retrain'] = True
        out['reasons'].append(
            f'Drift {drift*100:.0f}% supera el umbral 30% '
            f'(ensemble desacuerda con humanos).'
        )
        out['urgency'] = 'high' if drift > 0.45 else 'medium'
    if verdicts_since_train >= 200:
        out['should_retrain'] = True
        out['reasons'].append(
            f'{verdicts_since_train} verdicts nuevos desde el último train.'
        )
        out['urgency'] = max(out['urgency'], 'medium', key=_urg_rank)
    if last_train_at:
        try:
            import datetime as _dt
            try:
                tstamp = _dt.datetime.fromisoformat(str(last_train_at).replace('Z', '+00:00'))
            except Exception:
                tstamp = None
            if tstamp:
                delta = (_dt.datetime.now(tstamp.tzinfo) - tstamp).days
                if delta >= 30:
                    out['should_retrain'] = True
                    out['reasons'].append(f'Último train hace {delta} días.')
        except Exception:
            pass
    if not out['reasons']:
        out['reasons'].append('Modelo dentro de parámetros normales.')
    return out


def _urg_rank(s: str) -> int:
    return {'low': 0, 'medium': 1, 'high': 2}.get(s, 0)


# ──────────────────────────────────────────────────────────────────────
# 4. Auto-suggest learn-fp.
#
# Encuentra los paths/nombres más frecuentes en scan_results donde el
# scan padre tiene verdict=clean (la IA flageó pero el staff descartó).
# Esos son candidatos perfectos para automatizar como learn-fp por
# parte de admin.
#
# Solo considera last 30 días para no proponer cosas viejas.
# ──────────────────────────────────────────────────────────────────────
def suggest_learn_fp_candidates(
    cursor,
    company_id: Optional[int] = None,
    limit: int = 20,
) -> list:
    scope_key = f's:{company_id or 0}:{limit}'
    now = _time.time()
    cached = _suggest_cache.get(scope_key)
    if cached and now - cached[1] < _SUGGEST_TTL:
        return cached[0]
    candidates: list = []
    try:
        ph = _ph(cursor)
        params = []
        company_clause = ''
        if company_id:
            company_clause = f' AND s.company_id = {ph}'
            params.append(company_id)
        # PG: INTERVAL ; SQLite: datetime('now')
        try:
            cursor.execute(
                'SELECT LOWER(sr.issue_path) AS p, COUNT(*) AS n '
                'FROM scan_results sr JOIN scans s ON sr.scan_id = s.id '
                "WHERE s.verdict = 'clean' AND sr.issue_path IS NOT NULL "
                "  AND LENGTH(sr.issue_path) > 8 "
                "  AND sr.alert_level IN ('SOSPECHOSO', 'CRITICAL') "
                f'  AND s.verdict_at >= CURRENT_TIMESTAMP - INTERVAL \'30 days\' '
                f'  {company_clause} '
                f'GROUP BY LOWER(sr.issue_path) '
                f'HAVING COUNT(*) >= 3 '
                f'ORDER BY COUNT(*) DESC LIMIT {ph}',
                tuple(params + [limit])
            )
            rows = cursor.fetchall() or []
        except Exception:
            cursor.execute(
                'SELECT LOWER(sr.issue_path) AS p, COUNT(*) AS n '
                'FROM scan_results sr JOIN scans s ON sr.scan_id = s.id '
                "WHERE s.verdict = 'clean' AND sr.issue_path IS NOT NULL "
                "  AND LENGTH(sr.issue_path) > 8 "
                "  AND sr.alert_level IN ('SOSPECHOSO', 'CRITICAL') "
                f"  AND s.verdict_at >= datetime('now', '-30 days') "
                f'  {company_clause} '
                f'GROUP BY LOWER(sr.issue_path) '
                f'HAVING COUNT(*) >= 3 '
                f'ORDER BY COUNT(*) DESC LIMIT {ph}',
                tuple(params + [limit])
            )
            rows = cursor.fetchall() or []

        for r in rows:
            full = _rg(r, 0, 'p')
            n    = _rg(r, 1, 'n')
            if not full:
                continue
            # Sugerimos el último componente del path como fragmento
            # (suele ser el nombre del archivo o carpeta-archivo).
            full_norm = str(full).replace('/', '\\').strip()
            parts = full_norm.split('\\')
            fragment = '\\'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]
            candidates.append({
                'path_full':  full_norm[:255],
                'fragment':   fragment[:255],
                'count':      int(n or 0),
                'reason':     f'Aparece en {n} scans cerrados como clean (FP de la IA).',
            })
    except Exception as e:
        print(f'[ai_quality.suggest_learn_fp] {e}')
    _suggest_cache[scope_key] = (candidates, now)
    return candidates


# ──────────────────────────────────────────────────────────────────────
# 5. Bayesian smoothing helpers (utility para usar en otros módulos).
# ──────────────────────────────────────────────────────────────────────
def bayesian_smooth(success: int, total: int,
                    prior_success: float = 1.0,
                    prior_total: float   = 2.0) -> float:
    """Devuelve la tasa con smoothing Bayesiano (Beta prior).
    Útil para hash reputation, signal convergence, etc. con poca data.
    Ej: 1/2 → 0.50 (smoothed 1+1 / 2+2 = 0.50)
        9/10 → 0.83 (smoothed 9+1 / 10+2 = 0.833)
    """
    if total < 0:
        return 0.5
    return (success + prior_success) / (total + prior_total)
