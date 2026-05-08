"""ai_trust.py — Pack 32: módulo de Trust + Cooldown.

Implementa:
  * F#54  Staff Trust Score: cada moderador acumula histórico de
          agreements/disagreements con el ensemble verdict. Su
          trust_score (0-100) se computa con un Bayesian smoothing
          que parte de 50 (neutro) y se aleja a medida que tiene
          decisiones revisadas.
  * F#55  System 7 "Prior Consensus": en _compute_ensemble_verdict
          se inyecta un séptimo sistema que mira los verdicts previos
          del mismo machine_id/player y refuerza o atenúa el verdict
          actual con un peso de 0.10 (sin desplazar al gate).
  * F#60  Company FP Cooldown: si una empresa hace muchos overturns
          hack→clean o muchos learn-fp en 24h, sube un threshold_bump
          temporal a sus thresholds críticos para forzar revisión
          humana. Se decrementa con el tiempo.

Diseño:
  * Tablas idempotentes (CREATE IF NOT EXISTS) — no requiere migración
    manual ni Alembic.
  * Cache en memoria con TTL corto para lecturas hot-path.
  * Todas las operaciones de escritura aceptan un cursor opcional para
    poder co-existir con SAVEPOINTs y no romper la transacción
    principal si la tabla cae.
  * Compatible con Postgres y SQLite (sin sintaxis específica de
    Postgres en CREATE TABLE; UPSERT con try/except fallback).
"""

from __future__ import annotations

import time as _time
from typing import Optional


# ──────────────────────────────────────────────────────────────────────
# Cache simple en memoria con TTL.
# Invalidación: cualquier escritura llama a `_invalidate_*`.
# ──────────────────────────────────────────────────────────────────────
_TRUST_TTL = 120.0          # 2 min — staff_trust es semi-estática
_COOLDOWN_TTL = 60.0        # 1 min — cooldown se mueve más rápido
_PRIOR_TTL = 30.0           # 30s — prior consensus puede cambiar mid-scan

_trust_cache: dict = {}      # {user_id: (data_dict, ts)}
_cooldown_cache: dict = {}   # {company_id: (data_dict, ts)}
_prior_cache: dict = {}      # {(machine_id, player): (data, ts)}


def _invalidate_trust(user_id: int) -> None:
    _trust_cache.pop(user_id, None)


def _invalidate_cooldown(company_id: int) -> None:
    _cooldown_cache.pop(company_id, None)


# ──────────────────────────────────────────────────────────────────────
# DDL — tablas idempotentes.
# Llamar al boot del app y al primer access de cada función.
# ──────────────────────────────────────────────────────────────────────
def ensure_trust_tables(cursor) -> None:
    """CREATE IF NOT EXISTS para staff_trust + company_fp_cooldown.

    No falla si ya existen. Diseñado para correr en el path de cada
    escritura como salvaguarda; si la tabla cayó, se recrea sola.
    """
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff_trust (
            user_id              INTEGER PRIMARY KEY,
            verdicts_total       INTEGER DEFAULT 0,
            agreements           INTEGER DEFAULT 0,
            disagreements        INTEGER DEFAULT 0,
            overturns_to_clean   INTEGER DEFAULT 0,
            overturns_to_hack    INTEGER DEFAULT 0,
            confirmed_correct    INTEGER DEFAULT 0,
            confirmed_wrong      INTEGER DEFAULT 0,
            last_verdict_at      TIMESTAMP,
            trust_score          REAL    DEFAULT 50.0,
            updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_fp_cooldown (
            company_id           INTEGER PRIMARY KEY,
            fp_count_24h         INTEGER DEFAULT 0,
            overturn_count_24h   INTEGER DEFAULT 0,
            threshold_bump       INTEGER DEFAULT 0,
            cooldown_until       TIMESTAMP,
            last_event_at        TIMESTAMP,
            updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


# ──────────────────────────────────────────────────────────────────────
# F#54 — Staff Trust Score.
#
# Bayesian-lite: trust_score parte en 50 (neutro). Cada decisión
# revisada (confirmed_correct / confirmed_wrong) mueve el score con un
# beta-distribution-style update.
#
# Fórmula:
#   alpha = 1 + agreements + 2 * confirmed_correct
#   beta  = 1 + disagreements + 2 * confirmed_wrong
#   trust = 100 * alpha / (alpha + beta)
#
# Los confirmed_* pesan doble porque son ground-truth post-revisión.
# Los agreements/disagreements son weak signals (puede ser que el
# staff tenía razón aunque difiera del ensemble; eso lo limpia
# confirmed_correct).
# ──────────────────────────────────────────────────────────────────────
def _compute_trust_from_counts(d: dict) -> float:
    a = float(d.get('agreements')         or 0)
    di = float(d.get('disagreements')     or 0)
    cc = float(d.get('confirmed_correct') or 0)
    cw = float(d.get('confirmed_wrong')   or 0)
    alpha = 1.0 + a + 2.0 * cc
    beta  = 1.0 + di + 2.0 * cw
    if alpha + beta <= 0:
        return 50.0
    score = 100.0 * alpha / (alpha + beta)
    return max(0.0, min(100.0, round(score, 2)))


def get_staff_trust(cursor, user_id: int) -> dict:
    """Devuelve el dict de trust del staff. Caché 2min.

    Si la fila no existe, devuelve defaults sin escribir (lazy create
    en el primer update).
    """
    if not user_id:
        return _default_trust(0)
    now = _time.time()
    cached = _trust_cache.get(user_id)
    if cached and now - cached[1] < _TRUST_TTL:
        return cached[0]
    try:
        ensure_trust_tables(cursor)
        cursor.execute(
            'SELECT user_id, verdicts_total, agreements, disagreements, '
            'overturns_to_clean, overturns_to_hack, confirmed_correct, '
            'confirmed_wrong, trust_score, updated_at '
            f'FROM staff_trust WHERE user_id = {_ph(cursor)}',
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            data = _default_trust(user_id)
        else:
            data = {
                'user_id':            _rg(row, 0, 'user_id'),
                'verdicts_total':     int(_rg(row, 1, 'verdicts_total')     or 0),
                'agreements':         int(_rg(row, 2, 'agreements')         or 0),
                'disagreements':      int(_rg(row, 3, 'disagreements')      or 0),
                'overturns_to_clean': int(_rg(row, 4, 'overturns_to_clean') or 0),
                'overturns_to_hack':  int(_rg(row, 5, 'overturns_to_hack')  or 0),
                'confirmed_correct':  int(_rg(row, 6, 'confirmed_correct')  or 0),
                'confirmed_wrong':    int(_rg(row, 7, 'confirmed_wrong')    or 0),
                'trust_score':        float(_rg(row, 8, 'trust_score')      or 50.0),
                'updated_at':         str(_rg(row, 9, 'updated_at')         or ''),
            }
        _trust_cache[user_id] = (data, now)
        return data
    except Exception as e:
        print(f'[ai_trust.get_staff_trust] {e}')
        return _default_trust(user_id)


def _default_trust(user_id: int) -> dict:
    return {
        'user_id':            user_id,
        'verdicts_total':     0,
        'agreements':         0,
        'disagreements':      0,
        'overturns_to_clean': 0,
        'overturns_to_hack':  0,
        'confirmed_correct':  0,
        'confirmed_wrong':    0,
        'trust_score':        50.0,
        'updated_at':         '',
    }


def update_staff_trust_on_verdict(
    cursor,
    user_id: int,
    human_verdict: str,
    ensemble_verdict: str,
    prior_human_verdict: Optional[str] = None,
) -> None:
    """Llamar después de que el staff cierre un veredicto.

    Compara human_verdict (clean|hack|pending) contra el ensemble
    (LIMPIO|POCO_SOSPECHOSO|SOSPECHOSO|MUY_SOSPECHOSO|HACK_CONFIRMADO).
    Maps:
        ensemble HACK_CONFIRMADO/MUY_SOSPECHOSO  → 'hack'
        ensemble LIMPIO/POCO_SOSPECHOSO          → 'clean'
        ensemble SOSPECHOSO                      → 'ambiguous' (no cuenta)
    """
    if not user_id or human_verdict == 'pending':
        return
    if human_verdict not in ('clean', 'hack'):
        return

    # Map ensemble verdict → categoría binaria
    e = (ensemble_verdict or '').upper()
    if e in ('HACK_CONFIRMADO', 'MUY_SOSPECHOSO'):
        ensemble_bin = 'hack'
    elif e in ('LIMPIO', 'POCO_SOSPECHOSO'):
        ensemble_bin = 'clean'
    else:
        # SOSPECHOSO o desconocido → ambiguo, no contamos.
        return

    agree = (human_verdict == ensemble_bin)
    overturn_to_clean = (human_verdict == 'clean'  and ensemble_bin == 'hack')
    overturn_to_hack  = (human_verdict == 'hack'   and ensemble_bin == 'clean')

    # Re-confirmaciones (humano cambió de idea y volvió a coincidir o no
    # con el ensemble). Si prior_human_verdict difiere del actual, eso
    # es señal de auto-correction, neutralizamos la decision anterior.
    is_self_correction = (
        prior_human_verdict in ('clean', 'hack') and
        prior_human_verdict != human_verdict
    )

    try:
        ensure_trust_tables(cursor)
        ph = _ph(cursor)
        # Idempotente UPSERT: intentamos UPDATE primero, si 0 rows
        # entonces INSERT. Más portable que ON CONFLICT.
        cursor.execute(
            f'UPDATE staff_trust SET '
            f'  verdicts_total     = verdicts_total + 1, '
            f'  agreements         = agreements + {ph}, '
            f'  disagreements      = disagreements + {ph}, '
            f'  overturns_to_clean = overturns_to_clean + {ph}, '
            f'  overturns_to_hack  = overturns_to_hack + {ph}, '
            f'  last_verdict_at    = CURRENT_TIMESTAMP, '
            f'  updated_at         = CURRENT_TIMESTAMP '
            f'WHERE user_id = {ph}',
            (
                1 if agree else 0,
                0 if agree else 1,
                1 if overturn_to_clean else 0,
                1 if overturn_to_hack  else 0,
                user_id,
            )
        )
        # Compatibilidad: rowcount no es siempre confiable en PG; intentamos
        # SELECT después del UPDATE para saber si la fila existe.
        cursor.execute(
            f'SELECT user_id FROM staff_trust WHERE user_id = {ph}',
            (user_id,)
        )
        if not cursor.fetchone():
            cursor.execute(
                f'INSERT INTO staff_trust '
                f'  (user_id, verdicts_total, agreements, disagreements, '
                f'   overturns_to_clean, overturns_to_hack, last_verdict_at) '
                f'VALUES ({ph}, 1, {ph}, {ph}, {ph}, {ph}, CURRENT_TIMESTAMP)',
                (
                    user_id,
                    1 if agree else 0,
                    0 if agree else 1,
                    1 if overturn_to_clean else 0,
                    1 if overturn_to_hack  else 0,
                )
            )

        # Recomputamos trust_score y lo persistimos.
        cursor.execute(
            'SELECT agreements, disagreements, confirmed_correct, '
            f'confirmed_wrong FROM staff_trust WHERE user_id = {ph}',
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            d = {
                'agreements':         int(_rg(row, 0, 'agreements')         or 0),
                'disagreements':      int(_rg(row, 1, 'disagreements')      or 0),
                'confirmed_correct':  int(_rg(row, 2, 'confirmed_correct')  or 0),
                'confirmed_wrong':    int(_rg(row, 3, 'confirmed_wrong')    or 0),
            }
            score = _compute_trust_from_counts(d)
            cursor.execute(
                f'UPDATE staff_trust SET trust_score = {ph} WHERE user_id = {ph}',
                (score, user_id)
            )

        _invalidate_trust(user_id)
    except Exception as e:
        print(f'[ai_trust.update_staff_trust] {e}')


def confirm_staff_decision(
    cursor,
    user_id: int,
    was_correct: bool,
) -> None:
    """Llamar cuando un admin revisa POST-FACTO una decisión del staff
    y confirma si fue correcta o incorrecta. Pesa doble en el score.
    """
    if not user_id:
        return
    try:
        ensure_trust_tables(cursor)
        ph = _ph(cursor)
        col = 'confirmed_correct' if was_correct else 'confirmed_wrong'
        cursor.execute(
            f'UPDATE staff_trust SET {col} = {col} + 1, '
            f'  updated_at = CURRENT_TIMESTAMP '
            f'WHERE user_id = {ph}',
            (user_id,)
        )
        cursor.execute(
            f'SELECT user_id FROM staff_trust WHERE user_id = {ph}',
            (user_id,)
        )
        if not cursor.fetchone():
            cursor.execute(
                f'INSERT INTO staff_trust '
                f'  (user_id, {col}) VALUES ({ph}, 1)',
                (user_id,)
            )
        # Recompute
        cursor.execute(
            'SELECT agreements, disagreements, confirmed_correct, '
            f'confirmed_wrong FROM staff_trust WHERE user_id = {ph}',
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            d = {
                'agreements':         int(_rg(row, 0, 'agreements')         or 0),
                'disagreements':      int(_rg(row, 1, 'disagreements')      or 0),
                'confirmed_correct':  int(_rg(row, 2, 'confirmed_correct')  or 0),
                'confirmed_wrong':    int(_rg(row, 3, 'confirmed_wrong')    or 0),
            }
            score = _compute_trust_from_counts(d)
            cursor.execute(
                f'UPDATE staff_trust SET trust_score = {ph} WHERE user_id = {ph}',
                (score, user_id)
            )
        _invalidate_trust(user_id)
    except Exception as e:
        print(f'[ai_trust.confirm_staff_decision] {e}')


# ──────────────────────────────────────────────────────────────────────
# F#60 — Company FP Cooldown.
#
# Lógica:
#   * Cada learn-fp incrementa fp_count_24h.
#   * Cada overturn hack→clean incrementa overturn_count_24h.
#   * Si fp_count_24h >= 10 OR overturn_count_24h >= 5, threshold_bump
#     se eleva (+5 / +10 / +15 según severidad) y se programa
#     cooldown_until = now + 24h.
#   * En cada llamada se decae automáticamente: si han pasado >24h
#     desde last_event_at y cooldown_until ya venció, se resetean.
#   * El threshold_bump se SUMA a threshold_critical/suspicious de la
#     empresa para forzar que el staff esté más conservador.
# ──────────────────────────────────────────────────────────────────────
def get_company_cooldown(cursor, company_id: int) -> dict:
    """Devuelve el estado de cooldown de la empresa. Caché 1min."""
    if not company_id:
        return _default_cooldown(0)
    now = _time.time()
    cached = _cooldown_cache.get(company_id)
    if cached and now - cached[1] < _COOLDOWN_TTL:
        return cached[0]
    try:
        ensure_trust_tables(cursor)
        ph = _ph(cursor)
        cursor.execute(
            'SELECT company_id, fp_count_24h, overturn_count_24h, '
            'threshold_bump, cooldown_until, last_event_at '
            f'FROM company_fp_cooldown WHERE company_id = {ph}',
            (company_id,)
        )
        row = cursor.fetchone()
        if not row:
            data = _default_cooldown(company_id)
        else:
            data = {
                'company_id':         _rg(row, 0, 'company_id'),
                'fp_count_24h':       int(_rg(row, 1, 'fp_count_24h')       or 0),
                'overturn_count_24h': int(_rg(row, 2, 'overturn_count_24h') or 0),
                'threshold_bump':     int(_rg(row, 3, 'threshold_bump')     or 0),
                'cooldown_until':     str(_rg(row, 4, 'cooldown_until')     or ''),
                'last_event_at':      str(_rg(row, 5, 'last_event_at')      or ''),
            }
        # Decay: si last_event_at fue hace >24h, reseteamos counters.
        # Esto evita que la cooldown crezca por siempre con poco volumen.
        data = _maybe_decay_cooldown(cursor, data)
        _cooldown_cache[company_id] = (data, now)
        return data
    except Exception as e:
        print(f'[ai_trust.get_company_cooldown] {e}')
        return _default_cooldown(company_id)


def _default_cooldown(company_id: int) -> dict:
    return {
        'company_id':         company_id,
        'fp_count_24h':       0,
        'overturn_count_24h': 0,
        'threshold_bump':     0,
        'cooldown_until':     '',
        'last_event_at':      '',
    }


def _maybe_decay_cooldown(cursor, data: dict) -> dict:
    """Si last_event_at fue hace >24h, decae todo a 0.
    Implementado en SQL para que sea atómico y no requiera leer
    datetime parsing.
    """
    if not data.get('company_id'):
        return data
    if data.get('fp_count_24h', 0) == 0 and data.get('overturn_count_24h', 0) == 0:
        return data
    try:
        ph = _ph(cursor)
        # Decay: si han pasado >24h desde last_event_at, resetear.
        # Postgres: CURRENT_TIMESTAMP - INTERVAL '24 hours'
        # SQLite:   datetime('now', '-24 hours')
        try:
            cursor.execute(
                f'UPDATE company_fp_cooldown SET '
                f'  fp_count_24h = 0, overturn_count_24h = 0, '
                f'  threshold_bump = 0, '
                f'  updated_at = CURRENT_TIMESTAMP '
                f'WHERE company_id = {ph} '
                f"  AND last_event_at < CURRENT_TIMESTAMP - INTERVAL '24 hours'",
                (data['company_id'],)
            )
        except Exception:
            cursor.execute(
                f'UPDATE company_fp_cooldown SET '
                f'  fp_count_24h = 0, overturn_count_24h = 0, '
                f'  threshold_bump = 0 '
                f'WHERE company_id = {ph} '
                f"  AND last_event_at < datetime('now', '-24 hours')",
                (data['company_id'],)
            )
    except Exception as e:
        print(f'[ai_trust._maybe_decay] {e}')
    return data


def increment_cooldown(cursor, company_id: int, kind: str) -> None:
    """Llamar en learn-fp ('fp') o overturn hack→clean ('overturn').
    Recalcula threshold_bump según severidad.
    """
    if not company_id or kind not in ('fp', 'overturn'):
        return
    try:
        ensure_trust_tables(cursor)
        ph = _ph(cursor)
        col = 'fp_count_24h' if kind == 'fp' else 'overturn_count_24h'
        cursor.execute(
            f'UPDATE company_fp_cooldown SET '
            f'  {col} = {col} + 1, last_event_at = CURRENT_TIMESTAMP, '
            f'  updated_at = CURRENT_TIMESTAMP '
            f'WHERE company_id = {ph}',
            (company_id,)
        )
        cursor.execute(
            f'SELECT company_id FROM company_fp_cooldown WHERE company_id = {ph}',
            (company_id,)
        )
        if not cursor.fetchone():
            cursor.execute(
                f'INSERT INTO company_fp_cooldown '
                f'  (company_id, {col}, last_event_at) '
                f'VALUES ({ph}, 1, CURRENT_TIMESTAMP)',
                (company_id,)
            )
        # Recompute threshold_bump
        cursor.execute(
            'SELECT fp_count_24h, overturn_count_24h '
            f'FROM company_fp_cooldown WHERE company_id = {ph}',
            (company_id,)
        )
        row = cursor.fetchone()
        if row:
            fp = int(_rg(row, 0, 'fp_count_24h') or 0)
            ov = int(_rg(row, 1, 'overturn_count_24h') or 0)
            bump = _compute_threshold_bump(fp, ov)
            cursor.execute(
                f'UPDATE company_fp_cooldown SET threshold_bump = {ph} '
                f'WHERE company_id = {ph}',
                (bump, company_id)
            )
        _invalidate_cooldown(company_id)
    except Exception as e:
        print(f'[ai_trust.increment_cooldown] {e}')


def _compute_threshold_bump(fp_count: int, overturn_count: int) -> int:
    """Bumping table:
        fp_count >= 20 OR overturn_count >= 10 → +15 (alto)
        fp_count >= 10 OR overturn_count >=  5 → +10 (medio)
        fp_count >=  5 OR overturn_count >=  3 → +5  (bajo)
        else                                   → 0
    """
    if fp_count >= 20 or overturn_count >= 10:
        return 15
    if fp_count >= 10 or overturn_count >= 5:
        return 10
    if fp_count >= 5  or overturn_count >= 3:
        return 5
    return 0


# ──────────────────────────────────────────────────────────────────────
# F#55 — System 7: Prior Consensus.
#
# Mira los últimos N verdicts del mismo machine_id (o player) y devuelve
# un score 0-4 como los otros sistemas:
#   - Si los últimos 3+ verdicts cerrados son 'hack'   → 4
#   - Si la mayoría es 'hack'                          → 3
#   - Si la mayoría es 'clean'                         → 1 (atenúa)
#   - Si todos son 'clean' (3+)                        → 0
#   - Sin histórico                                    → 2 (neutro)
#
# Devuelve también la lista de verdicts previos para mostrar como
# explicación al staff.
# ──────────────────────────────────────────────────────────────────────
def system7_prior_consensus(
    cursor,
    machine_id: Optional[int],
    minecraft_username: Optional[str],
    exclude_scan_id: Optional[int] = None,
    lookback_n: int = 5,
) -> dict:
    """Score 0-4 + metadata.

    Considera scans cerrados (verdict IS NOT NULL AND verdict != 'pending')
    del mismo machine_id O mismo minecraft_username (case-insensitive),
    en los últimos `lookback_n`.
    """
    out = {
        'score':         2,        # neutro
        'verdicts':      [],       # lista de verdicts previos
        'count':         0,
        'hacks':         0,
        'cleans':        0,
        'reason':        'sin histórico previo',
    }
    if not machine_id and not minecraft_username:
        return out
    try:
        ph = _ph(cursor)
        clauses = []
        params = []
        if machine_id:
            clauses.append(f'machine_id = {ph}')
            params.append(machine_id)
        if minecraft_username:
            clauses.append(f'LOWER(minecraft_username) = {ph}')
            params.append(str(minecraft_username).lower())
        if not clauses:
            return out
        where = '(' + ' OR '.join(clauses) + ')'
        if exclude_scan_id:
            where += f' AND id <> {ph}'
            params.append(exclude_scan_id)
        # Solo verdicts cerrados (clean / hack) — pending no cuenta.
        cursor.execute(
            'SELECT verdict FROM scans WHERE ' + where +
            f"  AND verdict IN ('clean', 'hack') "
            f'  ORDER BY id DESC LIMIT {int(lookback_n)}',
            tuple(params)
        )
        rows = cursor.fetchall() or []
        verdicts = [str(_rg(r, 0, 'verdict') or '').lower() for r in rows]
        verdicts = [v for v in verdicts if v in ('clean', 'hack')]
        out['verdicts'] = verdicts
        out['count']    = len(verdicts)
        out['hacks']    = verdicts.count('hack')
        out['cleans']   = verdicts.count('clean')
        if not verdicts:
            return out
        if out['hacks'] >= 3 and out['hacks'] > out['cleans']:
            out['score']  = 4
            out['reason'] = f"{out['hacks']}/{out['count']} verdicts previos = HACK"
        elif out['hacks'] > out['cleans']:
            out['score']  = 3
            out['reason'] = f"mayoría hack ({out['hacks']}/{out['count']})"
        elif out['cleans'] >= 3 and out['cleans'] > out['hacks']:
            out['score']  = 0
            out['reason'] = f"{out['cleans']}/{out['count']} verdicts previos = CLEAN"
        elif out['cleans'] > out['hacks']:
            out['score']  = 1
            out['reason'] = f"mayoría clean ({out['cleans']}/{out['count']})"
        else:
            out['score']  = 2
            out['reason'] = f'empate {out["hacks"]}-{out["cleans"]} en últimos {out["count"]}'
        return out
    except Exception as e:
        print(f'[ai_trust.system7_prior_consensus] {e}')
        return out


# ──────────────────────────────────────────────────────────────────────
# Helpers internos (compatibilidad con app.py).
# ──────────────────────────────────────────────────────────────────────
def _ph(cursor) -> str:
    """Devuelve placeholder según driver. Usa atributo del cursor o
    default a '%s' (Postgres/MySQL). SQLite usa '?'.
    """
    try:
        # cursor.connection.__class__.__module__ contiene 'psycopg2' / 'sqlite3' / etc
        mod = cursor.connection.__class__.__module__.lower()
        if 'sqlite' in mod:
            return '?'
    except Exception:
        pass
    return '%s'


def _rg(row, idx: int, key: str):
    """row.get(key) si dict, row[idx] si tupla. Compatibilidad mixta."""
    if row is None:
        return None
    if hasattr(row, 'get'):
        return row.get(key) if row.get(key) is not None else (row.get(idx) if isinstance(row, dict) else None)
    try:
        return row[idx]
    except Exception:
        return None
