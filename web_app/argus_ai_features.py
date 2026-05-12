"""
Argus AI Features — Pack 45.

Feature extraction unificada para entrenar y predecir con los modelos de
`argus_ai_trainer`. La estrategia es:

  1. Cualquier predicción/training recibe un `evidence: dict` con todos los
     datos disponibles del jugador (violations recientes, history de scans,
     account metadata, scan results, reports, etc.).
  2. `extract_features(evidence)` devuelve un vector de floats de longitud
     `len(FEATURE_NAMES)`. Determinista: misma evidence → mismo vector.
  3. Los modelos se entrenan SIEMPRE sobre este vector. Esto garantiza que
     la forma de los features sea estable.

Las features están agrupadas por dominio:
  - Violation counts por check (16 features)
  - Severity stats (4 features)
  - Diversidad y clustering temporal (5 features)
  - Account & history (8 features)
  - Behavioral signals (10 features avanzadas)
  - Scanner outcomes (5 features)
  - Reports / cross-server (5 features)
  - Heuristic prior (1 feature)

Total: ~54 features. Bajado de 60 por practicidad — más es overfit.

Para extender: agregar nuevas keys a `_DEFAULT_FEATURES` con valor 0 y
agregar lógica en `extract_features`. Re-training automatico re-aprende
los pesos del nuevo feature space.
"""

from __future__ import annotations

import math
import os
import json
from typing import Any


# ──────────────────────────────────────────────────────────────────────
#  Vocabulario de checks (orden fijo — define la posición en el vector)
# ──────────────────────────────────────────────────────────────────────

KNOWN_CHECKS: list[str] = [
    "reach", "killaura_angle", "killaura_multi", "killaura_no_swing",
    "killaura_yaw_snap", "hit_through_wall", "autoclicker",
    "autoclicker_variance", "fly", "speed", "scaffold", "nofall",
    "jesus", "fasteat", "chat_spam", "cmd_spam", "inventory_move",
]

LEVEL_WEIGHTS = {"LOW": 1.0, "MID": 2.5, "HIGH": 5.0, "CRITICAL": 9.0}


def _load_legit_clients() -> set[str]:
    base = os.path.dirname(__file__)
    path = os.path.join(base, "static", "data", "legit_clients.json")
    defaults = {
        "lunarclient.exe", "lunar client.exe", "lunar client",
        "badlionclient.exe", "badlion client", "minecraftlauncher.exe",
        "minecraft.exe", "javaw.exe", "curseforge.exe",
    }
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        items = raw.get("process_names") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return defaults
        return {str(x).strip().lower() for x in items if str(x).strip()}
    except Exception:
        return defaults


_LEGIT_CLIENTS = _load_legit_clients()


# ──────────────────────────────────────────────────────────────────────
#  Lista completa de feature names (ORDEN IMPORTA — no reordenar)
# ──────────────────────────────────────────────────────────────────────

def _build_feature_names() -> list[str]:
    names: list[str] = []
    # 1) Per-check violation counts (weighted by severity)
    for c in KNOWN_CHECKS:
        names.append(f"v_{c}_score")
    # 2) Severity-level aggregates
    names += ["v_lows", "v_mids", "v_highs", "v_criticals"]
    # 3) Diversity & clustering
    names += [
        "distinct_checks", "total_violations",
        "cluster_density",       # cuán juntas vinieron las violations en tiempo
        "severity_escalation",   # ¿aumentó la severidad con el tiempo?
        "recent_window_density", # violations / segundo en la ventana reciente
    ]
    # 4) Account & history
    names += [
        "account_age_log_hours",
        "account_age_lt_24h",
        "account_age_lt_168h",
        "playtime_log_hours",
        "playtime_gt_50h",
        "playtime_gt_200h",
        "prior_clean_scans",
        "current_score",
    ]
    # 5) Behavioral signals (avanzadas)
    names += [
        "avg_cps",
        "cps_variance",
        "avg_reach",
        "reach_max",
        "hit_accept_rate",
        "yaw_stability_extreme",
        "pitch_stability_extreme",
        "movement_jitter",
        "session_length_hours",
        "first_seen_now",
        "legitimate_client_detected",
    ]
    # 6) Scanner outcomes
    names += [
        "scan_detected_hacks_recent",
        "scan_count_total",
        "scan_count_clean",
        "scan_count_positive",
        "scan_clean_ratio",
    ]
    # 7) Reports & cross-server
    names += [
        "reports_in_chat",
        "reports_log",
        "cross_server_violations",
        "cross_server_clean_streak",
        "is_first_time_in_argus_network",
    ]
    # 8) Heuristic prior
    names += ["heuristic_score"]
    return names


FEATURE_NAMES: list[str] = _build_feature_names()
N_FEATURES = len(FEATURE_NAMES)


# ──────────────────────────────────────────────────────────────────────
#  Extractor principal
# ──────────────────────────────────────────────────────────────────────

def extract_features(evidence: dict[str, Any]) -> list[float]:
    """
    Vector de floats de longitud `N_FEATURES`. Determinista.

    Acepta evidence con keys faltantes; rellena con 0.
    """
    fv: dict[str, float] = {n: 0.0 for n in FEATURE_NAMES}

    violations = evidence.get("violations") or []
    # 1) Per-check weighted score (sum of LEVEL_WEIGHTS por check)
    for v in violations:
        check = (v.get("check_name") or v.get("check") or "").strip()
        level = (v.get("level") or "LOW").upper()
        w = LEVEL_WEIGHTS.get(level, 1.0)
        # Decay por edad — violations viejas pesan menos
        age = float(v.get("age_seconds") or 0)
        decay = 1.0 if age < 60 else max(0.2, 0.5 ** (age / 600.0))
        contrib = w * decay
        if check in KNOWN_CHECKS:
            fv[f"v_{check}_score"] += contrib
        # 2) Severity aggregates
        if level == "LOW":      fv["v_lows"] += 1
        elif level == "MID":    fv["v_mids"] += 1
        elif level == "HIGH":   fv["v_highs"] += 1
        elif level == "CRITICAL": fv["v_criticals"] += 1

    # 3) Diversity & clustering
    distinct = set()
    for v in violations:
        c = (v.get("check_name") or v.get("check") or "").strip()
        if c:
            distinct.add(c)
    fv["distinct_checks"]   = float(len(distinct))
    fv["total_violations"]  = float(len(violations))

    if len(violations) >= 2:
        ages = [float(v.get("age_seconds") or 0) for v in violations]
        ages.sort()
        # Cluster density: 1 / (mean gap entre violations consecutivas)
        gaps = [ages[i+1] - ages[i] for i in range(len(ages)-1)]
        mean_gap = sum(gaps) / max(1, len(gaps)) if gaps else 60.0
        # Más densas (gap chico) → más score, max 1.0
        fv["cluster_density"] = clamp(1.0 - mean_gap / 60.0, 0.0, 1.0)
        # Severity escalation: comparar primera mitad vs segunda
        mid = len(violations) // 2
        def avg_sev(vs):
            if not vs: return 0.0
            return sum(LEVEL_WEIGHTS.get((v.get("level") or "LOW").upper(), 1.0)
                       for v in vs) / len(vs)
        first_half  = sorted(violations, key=lambda v: -(v.get("age_seconds") or 0))[:mid]
        second_half = sorted(violations, key=lambda v: -(v.get("age_seconds") or 0))[mid:]
        sev_diff = avg_sev(second_half) - avg_sev(first_half)
        fv["severity_escalation"] = clamp(sev_diff / 5.0, -1.0, 1.0)
        # Recent window density: violations en últimos 60s / 60
        recent = sum(1 for a in ages if a < 60)
        fv["recent_window_density"] = recent / 60.0
    else:
        fv["cluster_density"] = 0.0
        fv["severity_escalation"] = 0.0
        fv["recent_window_density"] = float(len(violations)) / 60.0

    # 4) Account & history
    aac = evidence.get("account_age_hours")
    if aac is not None:
        aac = max(0.0, float(aac))
        fv["account_age_log_hours"] = math.log1p(aac)
        fv["account_age_lt_24h"]    = 1.0 if aac < 24 else 0.0
        fv["account_age_lt_168h"]   = 1.0 if aac < 168 else 0.0

    pt = max(0.0, float(evidence.get("playtime_hours") or 0))
    fv["playtime_log_hours"] = math.log1p(pt)
    fv["playtime_gt_50h"]   = 1.0 if pt > 50 else 0.0
    fv["playtime_gt_200h"]  = 1.0 if pt > 200 else 0.0

    fv["prior_clean_scans"] = float(evidence.get("prior_clean_scans") or 0)
    fv["current_score"]     = clamp(float(evidence.get("current_score") or 0), 0.0, 1.0)

    # 5) Behavioral
    fv["avg_cps"]                = float(evidence.get("avg_cps") or 0)
    fv["cps_variance"]           = float(evidence.get("cps_variance") or 0)
    fv["avg_reach"]              = float(evidence.get("avg_reach") or 0)
    fv["reach_max"]              = float(evidence.get("reach_max") or 0)
    fv["hit_accept_rate"]        = clamp(float(evidence.get("hit_accept_rate") or 0), 0.0, 1.0)
    fv["yaw_stability_extreme"]  = 1.0 if evidence.get("yaw_stability_extreme") else 0.0
    fv["pitch_stability_extreme"] = 1.0 if evidence.get("pitch_stability_extreme") else 0.0
    fv["movement_jitter"]        = float(evidence.get("movement_jitter") or 0)
    fv["session_length_hours"]   = float(evidence.get("session_length_hours") or 0)
    fv["first_seen_now"]         = 1.0 if evidence.get("first_seen_now") else 0.0
    process_text = " ".join([
        str(evidence.get("process_tree") or ""),
        " ".join([str(p) for p in (evidence.get("processes") or [])]),
    ]).lower()
    fv["legitimate_client_detected"] = 1.0 if any(p in process_text for p in _LEGIT_CLIENTS) else 0.0

    # 6) Scanner outcomes
    fv["scan_detected_hacks_recent"] = 1.0 if evidence.get("scan_detected_hacks_recent") else 0.0
    sc_total = float(evidence.get("scan_count_total") or 0)
    sc_clean = float(evidence.get("scan_count_clean") or 0)
    sc_pos   = float(evidence.get("scan_count_positive") or 0)
    fv["scan_count_total"]   = sc_total
    fv["scan_count_clean"]   = sc_clean
    fv["scan_count_positive"] = sc_pos
    fv["scan_clean_ratio"]   = (sc_clean / sc_total) if sc_total > 0 else 0.5

    # 7) Reports & cross-server
    rep = max(0.0, float(evidence.get("reports_in_chat") or 0))
    fv["reports_in_chat"] = rep
    fv["reports_log"]     = math.log1p(rep)
    fv["cross_server_violations"]    = float(evidence.get("cross_server_violations") or 0)
    fv["cross_server_clean_streak"]  = float(evidence.get("cross_server_clean_streak") or 0)
    fv["is_first_time_in_argus_network"] = 1.0 if evidence.get("is_first_time_in_argus_network") else 0.0

    # 8) Heuristic prior
    fv["heuristic_score"] = clamp(float(evidence.get("heuristic_score") or 0), 0.0, 1.0)

    return [fv[n] for n in FEATURE_NAMES]


def extract_sequence(evidence: dict[str, Any]) -> list[str]:
    """
    Extrae secuencia ordenada de check_names del más antiguo al más reciente.

    El TemporalPatternDetector necesita esto.
    """
    violations = evidence.get("violations") or []
    # Más antiguo primero (age_seconds más grande → más viejo)
    sorted_v = sorted(violations, key=lambda v: -(v.get("age_seconds") or 0))
    return [v.get("check_name") or v.get("check") or "unknown"
            for v in sorted_v if (v.get("check_name") or v.get("check"))]


def evidence_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    """Resumen compacto del evidence para debugging / logging."""
    violations = evidence.get("violations") or []
    by_check: dict[str, dict[str, int]] = {}
    for v in violations:
        c = (v.get("check_name") or v.get("check") or "").strip()
        l = (v.get("level") or "LOW").upper()
        by_check.setdefault(c, {"LOW": 0, "MID": 0, "HIGH": 0, "CRITICAL": 0})
        by_check[c][l] = by_check[c].get(l, 0) + 1
    return {
        "total_violations": len(violations),
        "distinct_checks": len(by_check),
        "by_check": by_check,
        "account_age_hours": evidence.get("account_age_hours"),
        "playtime_hours": evidence.get("playtime_hours"),
        "prior_clean_scans": evidence.get("prior_clean_scans"),
    }


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# Para que el caller pueda obtener metadata
def feature_name_at(idx: int) -> str:
    return FEATURE_NAMES[idx] if 0 <= idx < N_FEATURES else f"unknown_{idx}"


def n_features() -> int:
    return N_FEATURES
