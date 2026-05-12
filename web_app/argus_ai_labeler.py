"""
Argus AI Labeler — Pack 45.

Sistema de auto-labeling que NO depende del staff para etiquetar decisiones
del AI Oracle como cheater/limpio. El staff es vago — el sistema piensa
solo.

Cada labeler retorna una lista de `AutoLabel`s con:
  - decision_id: a qué decisión del oracle se aplica
  - player_uuid / player_name
  - label: 0.0 (limpio) o 1.0 (cheater) o intermedio (soft)
  - confidence: cuánto confiamos en el auto-label (0..1)
  - source: identificador del pipeline (ej "ss_outcome_positive")
  - reasoning: texto humano

El trainer integra estos labels con peso = confidence. Labels explícitos
del staff tienen weight 1.0; auto-labels tienen 0.3-0.8 según fuente.

Los 12 pipelines:
  1. label_from_ss_outcomes     — SS posterior dio positivo/negativo
  2. label_from_manual_bans     — staff baneó tras decision
  3. label_from_unbans          — staff desbaneó (era FP)
  4. label_from_clean_history   — N días sin violations = limpio
  5. label_from_player_reports  — N reports de otros = cheater
  6. label_from_violation_clusters — clusters muy densos de HIGH/CRITICAL
  7. label_from_knn_propagation — vecino confirmado en feature space
  8. label_from_yaw_consistency — yaw extremadamente estable
  9. label_from_age_stats_mismatch — cuenta nueva con stats de pro
 10. label_from_hit_accept_rate — hit rate >99% sustained
 11. label_from_scanner_results — scanner desktop detectó cheats
 12. label_from_cross_server_history — historial en otros servers Argus

El motor de cada pipeline está aislado para que se pueda activar/desactivar
y debuggear por separado.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


# ──────────────────────────────────────────────────────────────────────
#  Estructuras
# ──────────────────────────────────────────────────────────────────────

@dataclass
class AutoLabel:
    """Una etiqueta auto-generada para un (decision_id, player) tupla."""
    decision_id: int | None
    player_uuid: str
    player_name: str
    label: float        # [0.0, 1.0]
    confidence: float   # [0.0, 1.0]
    source: str
    reasoning: str
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


# Confianza máxima por fuente — los pipelines no pueden producir más.
# Ajustable desde panel super-admin si se necesita relajar/endurecer.
SOURCE_MAX_CONFIDENCE = {
    "ss_outcome_positive":   0.95,  # SS reciente detectó hacks → cheater casi confirmado
    "ss_outcome_clean":      0.85,  # SS dijo limpio → fuerte señal pero falible (cheater apagó cheats)
    "manual_ban":            0.90,  # staff baneó → fuerte señal
    "manual_unban":          0.95,  # staff desbaneó → casi seguro era FP
    "clean_history_7d":      0.70,  # 7d sin violations
    "clean_history_30d":     0.85,  # 30d sin violations
    "player_reports":        0.55,  # reports de otros (puede ser troll)
    "violation_cluster":     0.65,  # clusters densos HIGH/CRITICAL
    "knn_propagation":       0.40,  # vecino cercano confirmado (medio débil)
    "yaw_extreme":           0.60,  # yaw extremadamente estable
    "age_stats_mismatch":    0.50,  # cuenta nueva con stats de pro
    "hit_accept_rate":       0.65,  # hit rate >99% sostenido
    "scanner_detected":      0.95,  # scanner desktop encontró cheats
    "cross_server_history":  0.70,  # baneado en otros servers Argus
}


# ──────────────────────────────────────────────────────────────────────
#  Pipelines individuales — cada uno es función pura que recibe data y
#  retorna lista de AutoLabel. La data viene del backend (queries SQL).
# ──────────────────────────────────────────────────────────────────────

def label_from_ss_outcomes(
    decisions: list[dict],     # decisiones AI sin label aún
    ss_results: dict[str, dict] # uuid → {'detected_hacks': bool, 'scan_at': ts}
) -> list[AutoLabel]:
    """
    Si una decisión del AI fue 'ss', 'kick' o 'ban', y POSTERIORMENTE
    se le hizo un SS al jugador (vía scanner desktop), el outcome del
    SS es señal muy fuerte.
    """
    out = []
    for d in decisions:
        uuid = d.get("player_uuid")
        if not uuid or uuid not in ss_results:
            continue
        r = ss_results[uuid]
        # SS debe ser posterior a la decisión
        if r.get("scan_at") and d.get("created_at") and r["scan_at"] <= d["created_at"]:
            continue
        if r.get("detected_hacks"):
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=uuid,
                player_name=d.get("player_name", ""),
                label=1.0,
                confidence=SOURCE_MAX_CONFIDENCE["ss_outcome_positive"],
                source="ss_outcome_positive",
                reasoning=f"SS posterior detectó cheats en {d.get('player_name')}",
            ))
        else:
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=uuid,
                player_name=d.get("player_name", ""),
                label=0.0,
                confidence=SOURCE_MAX_CONFIDENCE["ss_outcome_clean"],
                source="ss_outcome_clean",
                reasoning=f"SS posterior dio limpio en {d.get('player_name')}",
            ))
    return out


def label_from_manual_bans(
    decisions: list[dict],
    bans: list[dict]   # bans recientes con uuid + reason + banned_at
) -> list[AutoLabel]:
    """
    Si staff baneó manualmente al jugador < 24h después de la decision,
    es señal de cheater confirmado.
    """
    out = []
    ban_map = {b["player_uuid"]: b for b in bans if b.get("player_uuid")}
    for d in decisions:
        uuid = d.get("player_uuid")
        if not uuid or uuid not in ban_map:
            continue
        b = ban_map[uuid]
        decision_t = d.get("created_at") or 0
        ban_t = b.get("banned_at") or 0
        if ban_t < decision_t:
            continue
        delta_hours = (ban_t - decision_t) / 3600.0
        if delta_hours > 72:  # bans muy tardíos pueden ser por otra razón
            continue
        # Confianza modula por reason: si el reason mentions cheat/hack/kill = más alto
        reason = (b.get("reason") or "").lower()
        boost = 0.0
        if any(k in reason for k in ["cheat", "hack", "killaura", "fly", "speed",
                                     "scaffold", "ac ", "anti-cheat", "client"]):
            boost = 0.05
        out.append(AutoLabel(
            decision_id=d.get("id"),
            player_uuid=uuid,
            player_name=d.get("player_name", ""),
            label=1.0,
            confidence=min(0.99, SOURCE_MAX_CONFIDENCE["manual_ban"] + boost),
            source="manual_ban",
            reasoning=f"Staff baneó a {d.get('player_name')} {delta_hours:.1f}h después de decision. Reason: {reason[:80]}",
        ))
    return out


def label_from_unbans(
    decisions: list[dict],
    unbans: list[dict]
) -> list[AutoLabel]:
    """
    Si un jugador fue desbaneado tras la decisión del AI, era falso positivo.
    """
    out = []
    unban_map = {u["player_uuid"]: u for u in unbans if u.get("player_uuid")}
    for d in decisions:
        uuid = d.get("player_uuid")
        if uuid in unban_map and (d.get("action") in ("ban", "kick")):
            u = unban_map[uuid]
            reason = (u.get("reason") or "").lower()
            # Si motivo del unban menciona "false positive" / "FP" / "apelación", peso máximo
            extra = 0.0
            if any(k in reason for k in ["false positive", "fp", "apelaci", "appeal",
                                          "error", "mistake", "legit"]):
                extra = 0.05
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=uuid,
                player_name=d.get("player_name", ""),
                label=0.0,
                confidence=min(0.99, SOURCE_MAX_CONFIDENCE["manual_unban"] + extra),
                source="manual_unban",
                reasoning=f"Staff desbaneó a {d.get('player_name')}: {reason[:80]}",
            ))
    return out


def label_from_clean_history(
    decisions: list[dict],
    activity: dict[str, dict]   # uuid → {'last_violation_at': ts, 'last_seen_at': ts, 'days_active_after': int}
) -> list[AutoLabel]:
    """
    Si tras la decisión, el jugador SIGUIÓ jugando N días sin nuevas
    violations, era jugador limpio (al menos en su comportamiento).
    """
    out = []
    now = time.time()
    for d in decisions:
        uuid = d.get("player_uuid")
        if not uuid or uuid not in activity:
            continue
        a = activity[uuid]
        decision_t = d.get("created_at") or 0
        last_seen = a.get("last_seen_at") or 0
        last_violation = a.get("last_violation_at") or 0
        if last_seen < decision_t:
            continue
        days_active = (last_seen - decision_t) / 86400.0
        # No violations posteriores
        if last_violation >= decision_t:
            continue
        if days_active >= 30:
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=uuid,
                player_name=d.get("player_name", ""),
                label=0.0,
                confidence=SOURCE_MAX_CONFIDENCE["clean_history_30d"],
                source="clean_history_30d",
                reasoning=f"{d.get('player_name')} sigue activo {days_active:.0f}d sin más violations",
            ))
        elif days_active >= 7:
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=uuid,
                player_name=d.get("player_name", ""),
                label=0.0,
                confidence=SOURCE_MAX_CONFIDENCE["clean_history_7d"],
                source="clean_history_7d",
                reasoning=f"{d.get('player_name')} sigue activo {days_active:.0f}d sin más violations",
            ))
    return out


def label_from_player_reports(
    decisions: list[dict],
    reports: dict[str, list[dict]]  # uuid → list of report dicts
) -> list[AutoLabel]:
    """
    Si N+ jugadores distintos reportaron al jugador por cheats en chat
    o /report, sumar señal positiva.
    """
    out = []
    for d in decisions:
        uuid = d.get("player_uuid")
        if not uuid or uuid not in reports:
            continue
        reps = reports[uuid]
        # Filtrar reports cercanos a decision time (±3 días)
        decision_t = d.get("created_at") or 0
        relevant = [r for r in reps if abs((r.get("reported_at") or 0) - decision_t) < 3 * 86400]
        if len(relevant) < 3:
            continue
        # Reporters únicos
        unique_reporters = len({r.get("reporter_uuid") for r in relevant if r.get("reporter_uuid")})
        if unique_reporters < 3:
            continue
        # Más reporters → más confianza
        conf = min(SOURCE_MAX_CONFIDENCE["player_reports"], 0.30 + 0.05 * unique_reporters)
        out.append(AutoLabel(
            decision_id=d.get("id"),
            player_uuid=uuid,
            player_name=d.get("player_name", ""),
            label=1.0,
            confidence=conf,
            source="player_reports",
            reasoning=f"{d.get('player_name')} reportado por {unique_reporters} jugadores distintos",
        ))
    return out


def label_from_violation_clusters(
    decisions: list[dict]
) -> list[AutoLabel]:
    """
    Si la decisión incluyó muchas violations HIGH/CRITICAL en checks
    distintos en ventana corta (< 60s), es señal muy fuerte de cheater.
    """
    out = []
    for d in decisions:
        ev = d.get("evidence_summary") or {}
        v_critical = ev.get("v_criticals", 0)
        v_high     = ev.get("v_highs", 0)
        distinct   = ev.get("distinct_checks", 0)
        density    = ev.get("cluster_density", 0)
        # Muy denso + varios HIGH/CRITICAL en checks distintos
        score = 0.0
        if v_critical >= 1: score += 0.30
        if v_critical >= 2: score += 0.15
        if v_high >= 3:     score += 0.15
        if distinct >= 3:   score += 0.10
        if density >= 0.7:  score += 0.15
        if score < 0.50:
            continue
        out.append(AutoLabel(
            decision_id=d.get("id"),
            player_uuid=d.get("player_uuid", ""),
            player_name=d.get("player_name", ""),
            label=1.0,
            confidence=min(SOURCE_MAX_CONFIDENCE["violation_cluster"], score),
            source="violation_cluster",
            reasoning=f"Cluster denso: {v_critical} CRITICAL, {v_high} HIGH, "
                      f"{distinct} checks distintos, density={density:.2f}",
        ))
    return out


def label_from_knn_propagation(
    decisions: list[dict],
    knn_classifier   # KNNCheaterClassifier instance
) -> list[AutoLabel]:
    """
    Si el jugador es muy similar (sim > 0.92) a un perfil ya etiquetado
    explícitamente como cheater o limpio, propagar la etiqueta.

    Esto requiere que `decisions[i]` tenga `feature_vector` (lista de floats).
    """
    out = []
    if knn_classifier is None or knn_classifier.size() < 5:
        return out
    for d in decisions:
        fv = d.get("feature_vector")
        if not fv:
            continue
        # Probar predicción
        try:
            r = knn_classifier.predict(fv)
        except Exception:
            continue
        # Si el top-K mayoritariamente concuerda y el más cercano tiene sim > 0.92
        neighbors = r.get("neighbors") or []
        if not neighbors:
            continue
        top = neighbors[0]
        if top.get("similarity", 0) < 0.92:
            continue
        # Si el top-3 concuerda en label
        votes = [n.get("label", 0.5) for n in neighbors[:3]]
        if not votes:
            continue
        avg = sum(votes) / len(votes)
        if avg >= 0.85:
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=d.get("player_uuid", ""),
                player_name=d.get("player_name", ""),
                label=1.0,
                confidence=SOURCE_MAX_CONFIDENCE["knn_propagation"] * top["similarity"],
                source="knn_propagation",
                reasoning=f"Perfil muy similar (sim={top['similarity']:.2f}) a cheater confirmado: {top.get('player_name')}",
            ))
        elif avg <= 0.15:
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=d.get("player_uuid", ""),
                player_name=d.get("player_name", ""),
                label=0.0,
                confidence=SOURCE_MAX_CONFIDENCE["knn_propagation"] * top["similarity"],
                source="knn_propagation",
                reasoning=f"Perfil muy similar (sim={top['similarity']:.2f}) a limpio confirmado: {top.get('player_name')}",
            ))
    return out


def label_from_yaw_consistency(
    decisions: list[dict]
) -> list[AutoLabel]:
    """
    Si el jugador tuvo yaw_stability_extreme=True (rotación demasiado precisa
    para humano), es señal de killaura/aim assist.
    """
    out = []
    for d in decisions:
        ev = d.get("evidence_summary") or {}
        if ev.get("yaw_stability_extreme"):
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=d.get("player_uuid", ""),
                player_name=d.get("player_name", ""),
                label=0.85,  # soft label — sólo señal, no certeza
                confidence=SOURCE_MAX_CONFIDENCE["yaw_extreme"],
                source="yaw_extreme",
                reasoning=f"{d.get('player_name')} yaw stability extrema (aim-bot pattern)",
            ))
    return out


def label_from_age_stats_mismatch(
    decisions: list[dict]
) -> list[AutoLabel]:
    """
    Cuenta < 24h con CPS sostenido > 12 y reach > 4.2 = altamente
    sospechoso. Nadie hace eso en su primer día.
    """
    out = []
    for d in decisions:
        ev = d.get("evidence_summary") or {}
        age = ev.get("account_age_hours") or 999999
        cps = ev.get("avg_cps") or 0
        reach = ev.get("avg_reach") or 0
        if age < 24 and cps > 12 and reach > 4.2:
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=d.get("player_uuid", ""),
                player_name=d.get("player_name", ""),
                label=0.85,
                confidence=SOURCE_MAX_CONFIDENCE["age_stats_mismatch"],
                source="age_stats_mismatch",
                reasoning=f"Cuenta de {age:.0f}h con stats de veterano (cps={cps:.0f}, reach={reach:.2f})",
            ))
    return out


def label_from_hit_accept_rate(
    decisions: list[dict]
) -> list[AutoLabel]:
    """
    Si el jugador tuvo >99% hit accept rate sostenido en >50 hits, es bot
    pattern (humanos fallan 15-30% de hits por miss-clicks o desync).
    """
    out = []
    for d in decisions:
        ev = d.get("evidence_summary") or {}
        rate = ev.get("hit_accept_rate") or 0
        total = ev.get("total_hits") or 0
        if rate >= 0.99 and total >= 50:
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=d.get("player_uuid", ""),
                player_name=d.get("player_name", ""),
                label=0.90,
                confidence=SOURCE_MAX_CONFIDENCE["hit_accept_rate"],
                source="hit_accept_rate",
                reasoning=f"Hit accept rate {rate*100:.0f}% en {total} hits (humanly impossible)",
            ))
    return out


def label_from_scanner_results(
    decisions: list[dict],
    scanner_outcomes: dict[str, dict]   # uuid → {'detected_processes': [...], 'detected_at': ts, 'severity': 'HIGH'}
) -> list[AutoLabel]:
    """
    El scanner desktop tiene detecciones de procesos (Vape, Wurst, etc.),
    archivos de mods conocidos, hashes maliciosos. Es la fuente más fuerte.
    """
    out = []
    for d in decisions:
        uuid = d.get("player_uuid")
        if not uuid or uuid not in scanner_outcomes:
            continue
        s = scanner_outcomes[uuid]
        detected = s.get("detected_processes") or []
        files = s.get("detected_files") or []
        severity = (s.get("severity") or "LOW").upper()
        if not detected and not files:
            continue
        # Si el scanner detectó algo, es cheater con confianza altísima
        conf = SOURCE_MAX_CONFIDENCE["scanner_detected"]
        if severity == "LOW":  conf = 0.70
        if severity == "MID":  conf = 0.85
        out.append(AutoLabel(
            decision_id=d.get("id"),
            player_uuid=uuid,
            player_name=d.get("player_name", ""),
            label=1.0,
            confidence=conf,
            source="scanner_detected",
            reasoning=f"Scanner detectó: {', '.join((detected + files)[:5])}",
        ))
    return out


def label_from_cross_server_history(
    decisions: list[dict],
    cross_server: dict[str, dict]   # uuid → {'banned_in_servers': [...], 'clean_streak_days': int}
) -> list[AutoLabel]:
    """
    Si el jugador ya está baneado por cheats en OTROS servers de la red
    Argus, es señal muy fuerte. Si tiene un clean streak grande en varios
    servers, es señal limpia.
    """
    out = []
    for d in decisions:
        uuid = d.get("player_uuid")
        if not uuid or uuid not in cross_server:
            continue
        cs = cross_server[uuid]
        banned_servers = cs.get("banned_in_servers") or []
        clean_streak = cs.get("clean_streak_days") or 0
        if len(banned_servers) >= 2:
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=uuid,
                player_name=d.get("player_name", ""),
                label=1.0,
                confidence=min(0.95, SOURCE_MAX_CONFIDENCE["cross_server_history"]
                               + 0.05 * len(banned_servers)),
                source="cross_server_history",
                reasoning=f"Baneado por cheats en {len(banned_servers)} servers Argus",
            ))
        elif clean_streak >= 60:
            out.append(AutoLabel(
                decision_id=d.get("id"),
                player_uuid=uuid,
                player_name=d.get("player_name", ""),
                label=0.0,
                confidence=SOURCE_MAX_CONFIDENCE["cross_server_history"],
                source="cross_server_history",
                reasoning=f"{clean_streak} días limpios en otros servers Argus",
            ))
    return out


# ──────────────────────────────────────────────────────────────────────
#  Combinación: dedup + priorización
# ──────────────────────────────────────────────────────────────────────

def combine_labels(labels: list[AutoLabel]) -> dict[int, AutoLabel]:
    """
    Si hay varias labels para la misma decision_id, combinarlas:
      - Si todas concuerdan, usar la de mayor confidence.
      - Si difieren, usar promedio ponderado por confidence con `weighted_label`.
      - Si fuentes muy fuertes (>0.85) disagree, marcar como `uncertain`
        y reducir confidence.

    Devuelve dict {decision_id: AutoLabel_final}.
    """
    by_decision: dict[int, list[AutoLabel]] = {}
    for l in labels:
        if l.decision_id is None:
            continue
        by_decision.setdefault(l.decision_id, []).append(l)

    out: dict[int, AutoLabel] = {}
    for did, ls in by_decision.items():
        if len(ls) == 1:
            out[did] = ls[0]
            continue
        # Combinar
        total_w = sum(l.confidence for l in ls)
        if total_w < 1e-9:
            out[did] = ls[0]
            continue
        weighted_label = sum(l.label * l.confidence for l in ls) / total_w
        # Si disagree fuerte (alguna muy positiva y otra muy negativa con conf alta)
        strong_pos = [l for l in ls if l.confidence > 0.7 and l.label >= 0.7]
        strong_neg = [l for l in ls if l.confidence > 0.7 and l.label <= 0.3]
        # Confidence del resultado: alta concordancia → alta. Disagreement fuerte → baja.
        if strong_pos and strong_neg:
            confidence = 0.35
            reasoning = (f"DISAGREEMENT entre {len(strong_pos)} fuentes pos "
                         f"y {len(strong_neg)} neg: " +
                         " | ".join(f"{l.source}={l.label:.1f}" for l in ls[:4]))
        else:
            # Confidence promedio + boost por # fuentes que concuerdan
            confidence = min(0.99, total_w / len(ls) * (1.0 + 0.05 * len(ls)))
            reasoning = " + ".join(f"{l.source}({l.label:.1f}|{l.confidence:.2f})"
                                   for l in ls[:5])

        sample = ls[0]
        out[did] = AutoLabel(
            decision_id=did,
            player_uuid=sample.player_uuid,
            player_name=sample.player_name,
            label=weighted_label,
            confidence=confidence,
            source="combined",
            reasoning=reasoning,
            created_at=time.time(),
        )
    return out


def confidence_threshold_for_training(label_source: str) -> float:
    """
    Mínima confidence requerida para que un auto-label sea usable en training.
    Por defecto 0.45 — labels muy débiles son ruido.
    """
    base = 0.45
    if label_source.startswith("manual_") or label_source.startswith("scanner_"):
        return 0.50
    if label_source == "combined":
        return 0.40
    return base
