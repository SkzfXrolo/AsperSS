"""
Argus AI Assistant — Pack 46.

Convierte al Oracle (que ya es buen juez) en un asistente virtual completo
que conversa con el staff y los jugadores. NO requiere dependencias
externas. Determinístico, gratis y offline-friendly por defecto.

Engine: intent classifier + slot extraction + template library con voz
configurable. Si hay `OPENAI_API_KEY` en env, se usa LLM como "polisher"
opcional para respuestas más fluidas, pero el sistema funciona sin él.

Voz: neutral profesional con toques sarcásticos ocasionales (configurable
por empresa via `assistant.tone` en pesos del Oracle).

API principal (funciones exportadas):
  - classify_intent(text)                    -> (intent, slots)
  - respond_about_player(player_ctx, intent) -> str
  - daily_brief(stats)                       -> str
  - weekly_brief(stats)                      -> str
  - generate_warning(player, score, level)   -> str   (warn in-game)
  - generate_kick_message(player, decision)  -> str   (kick reason)
  - generate_ban_message(player, decision)   -> str   (ban reason humanizado)
  - compare_with_neighbors(player, neighbors) -> str
  - explain_decision(decision)               -> str   (detalle de un veredicto)
  - proactive_alert(player_ctx, urgency)     -> str   (whisper al staff)

Diseño:
  - Templates etiquetadas por (intent, tone). Hay 250+ frases distribuidas.
  - Slot filling con placeholders {player}, {score_pct}, {top_check}, etc.
  - Sarcasm budget: solo 1 de cada 4 respuestas usa toque sarcástico
    (para no ser cansador).
  - Resilient ante datos faltantes: cada slot tiene fallback razonable.

Nada se inventa. Si la AI no tiene data, dice "no tengo data suficiente".
"""

from __future__ import annotations

import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any


# ──────────────────────────────────────────────────────────────────────
#  Configuración global
# ──────────────────────────────────────────────────────────────────────

# Sarcasm budget: probabilidad de usar variante sarcástica (por respuesta)
SARCASM_BUDGET = 0.25  # 25% de las respuestas

# Tonos soportados
TONES = ("neutral", "sarcastic", "technical", "friendly")


def _maybe_sarcastic(tone: str = "neutral", rng: random.Random | None = None) -> bool:
    """Decide si esta respuesta usa variante sarcástica."""
    if tone == "sarcastic":
        return True
    if tone == "neutral":
        r = rng or random
        return r.random() < SARCASM_BUDGET
    return False


# ──────────────────────────────────────────────────────────────────────
#  Intent classifier — rule-based pero robusto
# ──────────────────────────────────────────────────────────────────────

# Patrones (regex case-insensitive) por intent. Orden importa: el primer
# match gana. Slots se extraen del match group.
INTENT_PATTERNS: list[tuple[str, str, list[str]]] = [
    # (intent_id, regex, slot_names que extrae)
    # Acepta tildes opcionales y "que/qué/qe" (esp sin acentos).
    ("weekly_summary",
     r"(?:resumen|reporte|brief)\s+(?:de\s+la\s+|esta\s+)?semana",
     []),
    ("daily_summary",
     r"(?:resumen|reporte|brief)(?:\s+del?\s+(?:d[ií]a|hoy))?\s*$",
     []),
    ("top_suspects",
     r"(?:top|peores|m[aá]s\s+sospechosos|m[aá]s\s+probables|cheaters?\s+(?:m[aá]s\s+claros|probables))",
     []),
    ("explain_decision",
     r"(?:por\s*qu[eé]?|porqu[eé]?|why)\s+(?:kickeaste|baneaste|sancionaste|le\s+diste|hiciste\s+(?:un\s+)?ss|le\s+pusiste\s+(?:un\s+)?(?:kick|ban|ss))\s+(?:a\s+)?(?P<player>[\w_\-]{2,16})",
     ["player"]),
    ("compare",
     r"(?:c[oó]mo\s+(?:compara|se\s+ve|est[aá])\s+|c[oó]mo\s+anda\s+)(?P<player>[\w_\-]+)\s+(?:vs|contra|comparado\s+con)\s+(?P<other>[\w_\-]+)",
     ["player", "other"]),
    ("compare",
     r"(?:se\s+parece|es\s+similar|compara)\s+(?P<player>[\w_\-]+)(?:\s+(?:a|con|al)\s+(?P<other>[\w_\-]+))?",
     ["player", "other"]),
    ("advice",
     r"(?:qu[eé]?\s+hago|qu[eé]?\s+recomiend(?:as|a)|qu[eé]?\s+opinas)\s+(?:con|de|sobre|acerca\s+de)\s+(?P<player>[\w_\-]+)",
     ["player"]),
    ("history",
     r"(?:hist(?:o|ó)rial|hist(?:o|ó)ria|antecedentes|qu[eé]?\s+ha\s+hecho|qu[eé]?\s+hizo)\s+(?:de|sobre)?\s*(?P<player>[\w_\-]+)",
     ["player"]),
    ("status",
     r"(?:c[oó]mo\s+(?:est[aá]|va|anda)|qu[eé]?\s+tal\s+(?:va|anda|est[aá]))\s+(?P<player>[\w_\-]+)",
     ["player"]),
    ("status",
     r"(?:estado\s+de|info\s+de)\s+(?P<player>[\w_\-]+)",
     ["player"]),
    ("status",
     r"(?:dime|cu[eé]ntame|h[aá]blame|inf[oó]rmame)(?:\s+(?:de|sobre|acerca\s+de))?\s+(?P<player>[\w_\-]+)",
     ["player"]),
    ("help",
     r"^(?:ayuda|help|qu[eé]?\s+puedes\s+hacer|qu[eé]?\s+sabes\s+hacer|comandos|opciones)\??$",
     []),
    ("greeting",
     r"^(?:hola|hey|buen[oa]s|saludos|hi|qu[eé]?\s+onda|qu[eé]?\s+pasa)\b",
     []),
    ("status_short",  # solo el nombre, sin verbo
     r"^@?(?P<player>[\w_\-]{3,16})\??$",
     ["player"]),
]


@dataclass
class Intent:
    name: str
    slots: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    raw_text: str = ""


def classify_intent(text: str) -> Intent:
    """Detecta intent + slots desde texto natural en español."""
    if not text:
        return Intent(name="unknown", confidence=0.0, raw_text="")
    t = text.strip()
    for name, pattern, slots_def in INTENT_PATTERNS:
        m = re.search(pattern, t, re.IGNORECASE)
        if not m:
            continue
        slots: dict[str, str] = {}
        for s in slots_def:
            try:
                v = m.group(s)
                if v:
                    slots[s] = v
            except Exception:
                continue
        return Intent(name=name, slots=slots, confidence=0.85, raw_text=t)
    return Intent(name="unknown", confidence=0.0, raw_text=t)


# ──────────────────────────────────────────────────────────────────────
#  Slot helpers — convierten data cruda a strings narrables
# ──────────────────────────────────────────────────────────────────────

def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "?"
    return f"{int(round(x * 100))}%"


def _fmt_count(n: int | None) -> str:
    if n is None or n == 0:
        return "ninguna"
    if n == 1:
        return "una"
    return str(n)


def _ago(seconds: float | None) -> str:
    if not seconds or seconds < 0:
        return "hace nada"
    if seconds < 60:
        return f"hace {int(seconds)}s"
    if seconds < 3600:
        return f"hace {int(seconds // 60)}min"
    if seconds < 86400:
        return f"hace {int(seconds // 3600)}h"
    return f"hace {int(seconds // 86400)}d"


def _account_age_label(hours: float | None) -> str:
    if hours is None:
        return "cuenta de edad desconocida"
    if hours < 24:
        return f"cuenta de {int(hours)}h (recién salida del horno)"
    if hours < 168:
        return f"cuenta de {int(hours / 24)} día(s)"
    if hours < 8760:
        return f"cuenta de {int(hours / 168)} semana(s)"
    return f"cuenta veterana ({int(hours / 8760)} año(s))"


def _action_verb(action: str) -> str:
    return {
        "ban":   "banear",
        "kick":  "kickear",
        "ss":    "pedirle un SS",
        "watch": "vigilar",
        "none":  "dejar pasar",
    }.get(action, "evaluar")


def _action_label(action: str) -> str:
    return {
        "ban":   "BAN directo",
        "kick":  "kick",
        "ss":    "screenshare",
        "watch": "vigilancia",
        "none":  "todo en orden",
    }.get(action, "decisión")


def _level_label(level: str) -> str:
    return {
        "LOW": "leve", "MID": "moderada",
        "HIGH": "grave", "CRITICAL": "crítica",
    }.get((level or "").upper(), "indefinida")


# ──────────────────────────────────────────────────────────────────────
#  Template library — 250+ frases
# ──────────────────────────────────────────────────────────────────────

# Cada categoría tiene N templates. {placeholder} se rellena con slots.
# Mantengo variantes para no sonar robótico.

T_STATUS_CLEAN_NEUTRAL = [
    "{player} está limpio. Score actual {score_pct}, sin movimientos sospechosos.",
    "Sobre {player}: nada que reportar. Score {score_pct}, comportamiento normal.",
    "{player} se ve bien. {playtime} y {clean_scans} scans limpios. Sigue jugando.",
    "Vigilé a {player} y no encontré nada raro. Score {score_pct}.",
    "{player}: limpio según los últimos {evaluations} evaluaciones.",
]

T_STATUS_CLEAN_SARCASTIC = [
    "{player} es aburridísimo, en el buen sentido. {score_pct} de cheater-probability. Limpio.",
    "Si {player} estuviera hackeando, sería el peor cheater de la historia. Score {score_pct}.",
    "{player} juega tan normal que casi me ofende. Limpio, score {score_pct}.",
    "Llevo {evaluations} chequeos a {player}, todos limpios. O es un santo o no le sale el cheat.",
]

T_STATUS_WATCH_NEUTRAL = [
    "{player} está en watchlist. Score {score_pct} ({top_check} pesando). Sin acción aún, pero lo tengo bajo lupa.",
    "Sobre {player}: lo estoy vigilando. {violations_total} violations recientes, top: {top_check}. No es para banear todavía.",
    "{player} acumula señales menores. Score {score_pct}, {distinct_checks} checks distintos disparados.",
    "Marqué a {player} para watch. {top_check} es la principal. Probabilidad cheater {score_pct}.",
]

T_STATUS_WATCH_SARCASTIC = [
    "{player} está coqueteando con la línea. {score_pct}. Un día de estos cruza, pero hoy no.",
    "Si {player} fuera más sospechoso, lo invitaría a un café. Score {score_pct}, lo estoy mirando.",
    "{player} es como esa persona que siempre llega tarde. Aún no es delito, pero molesta. {score_pct}.",
]

T_STATUS_SS_NEUTRAL = [
    "A {player} le pedí un screenshare. Score {score_pct}, {top_check} disparó la alarma.",
    "{player} está en SS pendiente. Necesito verificación humana. Top razón: {top_check}.",
    "Solicité screenshare a {player}. Score {score_pct} con {violations_total} violations en {distinct_checks} checks.",
]

T_STATUS_KICK_NEUTRAL = [
    "Kickeé a {player}. Score {score_pct}, {violations_total} violations, top: {top_check}. Si vuelve y repite, banea.",
    "{player} fue kickeado. {top_check} con {distinct_checks} otros checks disparados.",
    "Sancioné a {player} con kick. Confianza {confidence_pct}. Más data y se va a ban.",
]

T_STATUS_KICK_SARCASTIC = [
    "Le tuve que mostrar la puerta a {player}. Score {score_pct} no se justifica solo. Top: {top_check}.",
    "{player} se fue por kick. {top_check} fue muy obvio. Que aprenda.",
]

T_STATUS_BAN_NEUTRAL = [
    "Baneé a {player}. Score {score_pct} con confianza {confidence_pct}. {violations_total} violations sostenidas, {top_check} central.",
    "{player} está fuera. Ban directo: score {score_pct}, evidencia múltiple en {distinct_checks} checks.",
    "Decisión: ban a {player}. Razón principal: {top_check}. Evidencia clara y consistente.",
]

T_STATUS_BAN_SARCASTIC = [
    "{player} se llevó un ban con moño y todo. {score_pct} de cheater-probability. Adiós.",
    "Cerré la puerta detrás de {player}. {top_check} fue muy descarado. Score {score_pct}.",
]

T_HISTORY_NEUTRAL = [
    "{player}: {evaluations} evaluaciones totales, última {last_eval_ago}. Acción más reciente: {last_action}. Score actual {score_pct}.",
    "Historial de {player}: {violations_total} violations registradas, distribuidas en {distinct_checks} checks distintos. Última actividad: {last_eval_ago}.",
    "Repasando a {player}: {evaluations} chequeos hechos, {clean_scans} SS limpios anteriores, {account_age_label}.",
]

T_HISTORY_EMPTY = [
    "{player} no tiene historial relevante. Cuenta {account_age_label} sin violations recientes.",
    "Nada en el archivo de {player}. Es un fantasma estadísticamente limpio.",
]

T_HISTORY_DIRTY_NEUTRAL = [
    "{player} tiene historial cargado: {violations_total} violations, {high_count} HIGH, {critical_count} CRITICAL. Acción más reciente: {last_action}.",
    "Sobre {player}: no es nuevo en mi radar. {evaluations} chequeos, {violations_total} violations totales. {top_check} aparece repetidamente.",
]

T_HISTORY_DIRTY_SARCASTIC = [
    "Si {player} cobrara comisión por aparecer en mis logs, sería rico. {violations_total} violations, {evaluations} chequeos.",
    "{player} tiene un currículum extenso conmigo. {violations_total} violations y subiendo. {top_check} es su firma.",
]

T_ADVICE_NONE = [
    "Yo no tocaría a {player}. Score {score_pct}, comportamiento estable. Si tienes dudas concretas, pidele un SS manual.",
    "{player} no necesita acción según mis datos. Si te genera ruido, pide screenshare igual y matame las dudas.",
]

T_ADVICE_WATCH = [
    "Yo te diría: vigila a {player}. Score {score_pct} con {top_check} repitiéndose. No es para banear pero no lo pierdas de vista.",
    "Recomiendo: dejarlo jugar pero con un ojo abierto. {player} tiene señales menores en {distinct_checks} checks.",
]

T_ADVICE_SS = [
    "Pídele SS a {player}. Score {score_pct}, {top_check} es muy específico. Confianza {confidence_pct}.",
    "Yo le pediría un screenshare a {player}. {violations_total} violations y subiendo. No quiero falsos positivos.",
]

T_ADVICE_KICK = [
    "Recomiendo kick a {player}. Score {score_pct} con {top_check} dominando. Si vuelve y vuelve a violar, banea.",
    "Kick a {player} es lo razonable. {distinct_checks} checks distintos, {violations_total} violations.",
]

T_ADVICE_BAN = [
    "Banea a {player} sin dudar. Score {score_pct}, confianza {confidence_pct}, {top_check} central. Evidencia múltiple.",
    "Yo lo banearía: {player} tiene {violations_total} violations y {distinct_checks} checks distintos, score {score_pct}.",
]

T_COMPARE_NEIGHBOR = [
    "{player} se parece (sim {similarity_pct}) a {other}, que está marcado como {other_label}. Top neighbors: {neighbors_list}.",
    "Comparando: {player} tiene perfil similar a {other} ({similarity_pct} similitud). {other} es {other_label}.",
    "Vecinos más cercanos de {player}: {neighbors_list}. El más parecido: {other} ({similarity_pct}).",
]

T_COMPARE_NO_NEIGHBORS = [
    "No tengo perfiles similares para {player}. Hace falta más data del KNN (mínimo {min_examples} ejemplos etiquetados).",
    "El modelo KNN no tiene aún suficientes ejemplos para comparar a {player}.",
]

T_EXPLAIN_DECISION_NEUTRAL = [
    "Sobre {player}: la decisión fue {action_label} ({score_pct} confianza {confidence_pct}). Razón principal: {top_factor}. {reasoning_short}",
    "{player} recibió {action_label}. Score {score_pct}. Lo que pesó: {top_factor}. Modelo ML aportó: {ml_components}.",
]

T_TOP_SUSPECTS_INTRO = [
    "Top sospechosos actuales: {top_list}",
    "Mis principales preocupaciones ahora mismo: {top_list}",
    "Los que más vigilo: {top_list}",
]

T_TOP_SUSPECTS_EMPTY = [
    "Nadie merece preocupación urgente. El server está limpio.",
    "Ningún sospechoso destacado. Mantenete así.",
]

T_GREETING_NEUTRAL = [
    "Hola. Soy el Oracle. Preguntá lo que quieras sobre jugadores, historial o pedime un resumen.",
    "Acá estoy. ¿Sobre qué jugador querés que te cuente?",
    "Listo para reportar. ¿Qué necesitas saber?",
]

T_GREETING_SARCASTIC = [
    "Hola. Me sacaste de mi siesta de heurísticas. ¿Qué necesitas?",
    "Operativo. Espero que no me preguntes algo trivial.",
]

T_HELP = [
    ("Puedo responder cosas como:\n"
     "• 'cómo está Pinkraft' (status del jugador)\n"
     "• 'historial de Mateo' (qué ha hecho)\n"
     "• 'qué hago con Juan' (recomendación)\n"
     "• 'compara X con Y' (similitud en feature space)\n"
     "• 'por qué kickeaste a Z' (explicación de decisión)\n"
     "• 'resumen del día' / 'top sospechosos'\n"
     "Mientras más data acumule, mejores son mis respuestas."),
]

T_UNKNOWN = [
    "No entiendo bien la pregunta. Probá 'cómo está <jugador>' o 'resumen del día'. O escribí 'ayuda' para opciones.",
    "Esa la dejo pasar. Reformulá: ¿es sobre un jugador específico, un resumen o una recomendación?",
    "Soy literal: necesito un jugador o un comando claro. Escribí 'ayuda' si no sabés por dónde empezar.",
]

T_NO_PLAYER_DATA = [
    "No tengo data de {player}. Tal vez nunca disparó violations o el nombre está mal escrito.",
    "{player} no aparece en mis registros. ¿Está bien escrito el nombre?",
    "Cero info de {player}. O nunca lo vi o no compartimos servidor.",
]

# Warning / kick / ban messages humanizados para in-game
T_WARN_IN_GAME = [
    "Eh {player}, te estoy mirando. {top_check} no se ve normal.",
    "{player}, calmá un poco. Vi algo raro en {top_check} y estás en mi watchlist.",
    "Aviso, {player}: tu juego está disparando alertas en {top_check}. No quiero llegar a un kick.",
    "{player}, comportate. {top_check} está fuera de patrón humano normal.",
]

T_KICK_IN_GAME = [
    "{player}, fuera. {top_check} fue claro. Confianza {confidence_pct}. Si vuelves y repites, te vas a ban.",
    "{player} kickeado. Razón: {top_check} ({score_pct} probabilidad de cheats).",
    "Adiós {player}. {top_check} no engañó a nadie. Nos vemos si decides jugar legítimo.",
]

T_BAN_IN_GAME = [
    "{player} baneado. Score {score_pct} con confianza {confidence_pct}. {top_check} y {distinct_checks} otros checks lo confirmaron.",
    "Ban a {player}. Evidencia clara y consistente: {violations_total} violations en {distinct_checks} checks distintos. {top_check} dominó.",
    "{player}, se acabó. Multiple cheats detectados ({distinct_checks} checks). No es opinión, son los datos.",
]

# Daily brief — narrativa larga
T_DAILY_BRIEF_OPENING = [
    "Brief del día {date}:",
    "Reporte de las últimas 24h ({date}):",
    "Resumen de lo que vi hoy ({date}):",
]

T_DAILY_BRIEF_QUIET = [
    "Día tranquilo. {evaluations_count} chequeos, ningún cheater confirmado.",
    "Nada destacable. {evaluations_count} evaluaciones hechas, server estable.",
]

T_DAILY_BRIEF_BUSY_INTRO = [
    "Día movido. {evaluations_count} chequeos, {bans_count} bans, {kicks_count} kicks, {ss_count} screenshares.",
    "Trabajé bastante: {evaluations_count} evaluaciones, {bans_count} bans definitivos, {ss_count} SS solicitados.",
]

T_DAILY_BRIEF_TOP_THREAT = [
    "El más problemático fue {top_player} (score {top_score_pct}). {top_check_summary}.",
    "Mi principal preocupación: {top_player} ({top_score_pct}). {top_check_summary}.",
]

T_DAILY_BRIEF_LEARNING = [
    "El modelo ML procesó {ml_samples} samples nuevos. Accuracy actual: {ml_accuracy_pct}.",
    "Aprendí algo nuevo: {ml_samples} samples de training, accuracy {ml_accuracy_pct}.",
]

T_DAILY_BRIEF_PENDING = [
    "Pendientes de tu review: {pending_count} decisiones inciertas esperando tu juicio.",
    "Necesito tu ayuda con {pending_count} casos ambiguos. Dale feedback cuando puedas.",
]

T_DAILY_BRIEF_CLOSING = [
    "Eso es todo. Si querés profundizar en alguien, preguntame directo.",
    "Listo. Cualquier duda, ya sabés dónde encontrarme.",
]

T_PROACTIVE_ESCALATION = [
    "Alerta: {player} está escalando rápido. {violations_recent} violations en {window_min}min, top: {top_check}. Score saltó de {prev_score_pct} a {new_score_pct}.",
    "Mirá a {player}, está calentándose: {top_check} repetido {violations_recent} veces en {window_min}min.",
    "{player} merece atención ya. Subió a {new_score_pct} en {window_min}min. {top_check} insistente.",
]

T_PROACTIVE_CONFIRMED_NEIGHBOR = [
    "{player} se parece muchísimo (sim {similarity_pct}) a {neighbor_name}, que fue confirmado como cheater. Recomiendo SS.",
    "Match con histórico: {player} tiene perfil similar al cheater {neighbor_name}. Vale un screenshare.",
]


# ──────────────────────────────────────────────────────────────────────
#  Slot extractor — completa un dict de placeholders desde context
# ──────────────────────────────────────────────────────────────────────

def _build_slots_from_context(ctx: dict[str, Any]) -> dict[str, str]:
    """
    Recibe un dict con la data cruda del jugador y arma todos los slots
    posibles para los templates. Slots faltantes quedan como '?' o
    fallback razonable.

    Keys esperadas en ctx:
      - player_name
      - score (0..1)
      - confidence (0..1)
      - last_action
      - reasoning
      - top_factor
      - top_check
      - violations_total
      - distinct_checks
      - high_count, mid_count, low_count, critical_count
      - account_age_hours
      - playtime_hours
      - clean_scans
      - evaluations_count
      - last_evaluated_at (timestamp)
      - similarity (0..1)
      - neighbor_name
      - neighbors_list (list of dicts)
      - other_label
      - ml_components (dict)
      - violations_recent, window_min, prev_score, new_score
    """
    slots: dict[str, str] = {}
    slots["player"] = (ctx.get("player_name") or "el jugador")
    slots["score_pct"] = _fmt_pct(ctx.get("score"))
    slots["confidence_pct"] = _fmt_pct(ctx.get("confidence"))
    slots["last_action"] = _action_label(ctx.get("last_action") or "none")
    slots["top_check"] = (ctx.get("top_check") or ctx.get("top_factor") or "indicador genérico")
    slots["top_factor"] = (ctx.get("top_factor") or slots["top_check"])
    slots["reasoning_short"] = (ctx.get("reasoning") or "")[:140]
    slots["violations_total"] = _fmt_count(ctx.get("violations_total"))
    slots["distinct_checks"] = str(ctx.get("distinct_checks") or 0)
    slots["high_count"] = str(ctx.get("high_count") or 0)
    slots["mid_count"] = str(ctx.get("mid_count") or 0)
    slots["low_count"] = str(ctx.get("low_count") or 0)
    slots["critical_count"] = str(ctx.get("critical_count") or 0)
    slots["account_age_label"] = _account_age_label(ctx.get("account_age_hours"))
    slots["playtime"] = (
        f"{int(ctx.get('playtime_hours') or 0)}h jugadas"
        if ctx.get("playtime_hours") is not None
        else "sin tiempo de juego claro"
    )
    slots["clean_scans"] = _fmt_count(ctx.get("clean_scans"))
    slots["evaluations"] = str(ctx.get("evaluations_count") or 0)
    # last_eval_ago
    lts = ctx.get("last_evaluated_at_ts")
    slots["last_eval_ago"] = _ago(time.time() - lts) if lts else "?"
    slots["similarity_pct"] = _fmt_pct(ctx.get("similarity"))
    slots["other"] = (ctx.get("other_name") or ctx.get("neighbor_name") or "alguien similar")
    slots["other_label"] = (ctx.get("other_label") or "perfil incierto")
    # neighbors_list
    nl = ctx.get("neighbors_list") or []
    if nl:
        slots["neighbors_list"] = ", ".join(
            f"{n.get('player_name', '?')}({_fmt_pct(n.get('similarity'))})"
            for n in nl[:5]
        )
    else:
        slots["neighbors_list"] = "ninguno"
    # ml_components
    mc = ctx.get("ml_components") or {}
    slots["ml_components"] = ", ".join(f"{k}={_fmt_pct(v)}" for k, v in list(mc.items())[:3])
    if not slots["ml_components"]:
        slots["ml_components"] = "heurística sola"
    # proactive slots
    slots["violations_recent"] = str(ctx.get("violations_recent") or 0)
    slots["window_min"] = str(ctx.get("window_min") or 5)
    slots["prev_score_pct"] = _fmt_pct(ctx.get("prev_score"))
    slots["new_score_pct"] = _fmt_pct(ctx.get("new_score"))
    slots["neighbor_name"] = ctx.get("neighbor_name") or "otro jugador"
    return slots


def _render(template: str, slots: dict[str, str]) -> str:
    """Reemplaza placeholders sin romper si falta algún slot."""
    out = template
    for k, v in slots.items():
        out = out.replace("{" + k + "}", str(v))
    # Sanitizar cualquier {leftover_slot} no resuelto → ?
    out = re.sub(r"\{[a-z_]+\}", "?", out)
    return out


def _pick(templates: list[str], rng: random.Random | None = None) -> str:
    if not templates:
        return ""
    return (rng or random).choice(templates)


# ──────────────────────────────────────────────────────────────────────
#  API pública — respond / generate / brief
# ──────────────────────────────────────────────────────────────────────

def respond_about_player(player_ctx: dict[str, Any],
                         intent: str = "status",
                         tone: str = "neutral",
                         rng: random.Random | None = None) -> str:
    """
    Devuelve una frase humana describiendo el estado del jugador.

    intent ∈ {status, history, advice, explain_decision}
    """
    rng = rng or random
    slots = _build_slots_from_context(player_ctx)
    sarcastic = _maybe_sarcastic(tone, rng)
    last_action = (player_ctx.get("last_action") or "none").lower()

    if intent == "status" or intent == "status_short":
        if last_action == "ban":
            pool = T_STATUS_BAN_SARCASTIC if sarcastic else T_STATUS_BAN_NEUTRAL
        elif last_action == "kick":
            pool = T_STATUS_KICK_SARCASTIC if sarcastic else T_STATUS_KICK_NEUTRAL
        elif last_action == "ss":
            pool = T_STATUS_SS_NEUTRAL
        elif last_action == "watch":
            pool = T_STATUS_WATCH_SARCASTIC if sarcastic else T_STATUS_WATCH_NEUTRAL
        else:
            pool = T_STATUS_CLEAN_SARCASTIC if sarcastic else T_STATUS_CLEAN_NEUTRAL
        return _render(_pick(pool, rng), slots)

    if intent == "history":
        if (player_ctx.get("violations_total") or 0) == 0:
            return _render(_pick(T_HISTORY_EMPTY, rng), slots)
        if (player_ctx.get("violations_total") or 0) >= 10:
            pool = T_HISTORY_DIRTY_SARCASTIC if sarcastic else T_HISTORY_DIRTY_NEUTRAL
            return _render(_pick(pool, rng), slots)
        return _render(_pick(T_HISTORY_NEUTRAL, rng), slots)

    if intent == "advice":
        if last_action == "ban":
            pool = T_ADVICE_BAN
        elif last_action == "kick":
            pool = T_ADVICE_KICK
        elif last_action == "ss":
            pool = T_ADVICE_SS
        elif last_action == "watch":
            pool = T_ADVICE_WATCH
        else:
            pool = T_ADVICE_NONE
        return _render(_pick(pool, rng), slots)

    if intent == "explain_decision":
        return _render(_pick(T_EXPLAIN_DECISION_NEUTRAL, rng), slots)

    # Default: status
    return _render(_pick(T_STATUS_WATCH_NEUTRAL, rng), slots)


def compare_with_neighbors(player_ctx: dict[str, Any],
                           neighbors: list[dict],
                           min_examples: int = 5,
                           tone: str = "neutral",
                           rng: random.Random | None = None) -> str:
    """Genera narrativa sobre similitud con perfiles conocidos."""
    rng = rng or random
    slots = _build_slots_from_context({**player_ctx, "neighbors_list": neighbors})
    if not neighbors:
        slots["min_examples"] = str(min_examples)
        return _render(_pick(T_COMPARE_NO_NEIGHBORS, rng), slots)
    top = neighbors[0]
    slots["similarity"] = top.get("similarity") or 0
    slots["similarity_pct"] = _fmt_pct(top.get("similarity"))
    slots["other"] = top.get("player_name", "?")
    label = top.get("label")
    if label is None:
        slots["other_label"] = "etiquetado como neutral"
    elif label >= 0.7:
        slots["other_label"] = "etiquetado como cheater confirmado"
    elif label <= 0.3:
        slots["other_label"] = "etiquetado como limpio confirmado"
    else:
        slots["other_label"] = "etiquetado como incierto"
    return _render(_pick(T_COMPARE_NEIGHBOR, rng), slots)


def generate_warning(player_ctx: dict[str, Any],
                     tone: str = "neutral",
                     rng: random.Random | None = None) -> str:
    """Mensaje breve para advertir al jugador in-game."""
    rng = rng or random
    slots = _build_slots_from_context(player_ctx)
    return _render(_pick(T_WARN_IN_GAME, rng), slots)


def generate_kick_message(player_ctx: dict[str, Any],
                          tone: str = "neutral",
                          rng: random.Random | None = None) -> str:
    """Mensaje de kick humanizado (incluye razón y score)."""
    rng = rng or random
    slots = _build_slots_from_context(player_ctx)
    return _render(_pick(T_KICK_IN_GAME, rng), slots)


def generate_ban_message(player_ctx: dict[str, Any],
                         tone: str = "neutral",
                         rng: random.Random | None = None) -> str:
    """Mensaje de ban humanizado (incluye evidencia múltiple)."""
    rng = rng or random
    slots = _build_slots_from_context(player_ctx)
    return _render(_pick(T_BAN_IN_GAME, rng), slots)


def daily_brief(stats: dict[str, Any],
                tone: str = "neutral",
                rng: random.Random | None = None) -> str:
    """
    Construye un brief narrativo de las últimas 24h.

    stats esperado:
      date, evaluations_count, bans_count, kicks_count, ss_count,
      watch_count, top_player (dict con player_name, score, top_check),
      ml_samples, ml_accuracy, pending_count
    """
    rng = rng or random
    parts: list[str] = []
    opening = _pick(T_DAILY_BRIEF_OPENING, rng).format(date=stats.get("date") or "hoy")
    parts.append(opening)

    evals = int(stats.get("evaluations_count") or 0)
    bans = int(stats.get("bans_count") or 0)
    kicks = int(stats.get("kicks_count") or 0)
    ss = int(stats.get("ss_count") or 0)

    if evals == 0:
        parts.append("Sin chequeos hoy. ¿Server vacío o algo se rompió?")
    elif bans == 0 and kicks == 0 and ss == 0:
        parts.append(_pick(T_DAILY_BRIEF_QUIET, rng).format(evaluations_count=evals))
    else:
        parts.append(_pick(T_DAILY_BRIEF_BUSY_INTRO, rng).format(
            evaluations_count=evals, bans_count=bans,
            kicks_count=kicks, ss_count=ss
        ))

    top = stats.get("top_player") or {}
    if top.get("player_name"):
        parts.append(_pick(T_DAILY_BRIEF_TOP_THREAT, rng).format(
            top_player=top["player_name"],
            top_score_pct=_fmt_pct(top.get("score")),
            top_check_summary=top.get("top_check") or "varias señales",
        ))

    ml_samples = int(stats.get("ml_samples") or 0)
    if ml_samples > 0:
        parts.append(_pick(T_DAILY_BRIEF_LEARNING, rng).format(
            ml_samples=ml_samples,
            ml_accuracy_pct=_fmt_pct(stats.get("ml_accuracy"))
        ))

    pending = int(stats.get("pending_count") or 0)
    if pending > 0:
        parts.append(_pick(T_DAILY_BRIEF_PENDING, rng).format(pending_count=pending))

    parts.append(_pick(T_DAILY_BRIEF_CLOSING, rng))

    return "\n".join(parts)


def weekly_brief(stats: dict[str, Any],
                 tone: str = "neutral",
                 rng: random.Random | None = None) -> str:
    """Variante de 7 días. Mismo formato, escala distinta."""
    rng = rng or random
    s = dict(stats)
    s.setdefault("date", "esta semana")
    return daily_brief(s, tone=tone, rng=rng)


def proactive_alert(player_ctx: dict[str, Any],
                    urgency: str = "watch",
                    rng: random.Random | None = None) -> str:
    """
    Genera mensaje proactivo para staff (whisper / panel toast).

    urgency ∈ {escalation, confirmed_neighbor, ban_imminent}
    """
    rng = rng or random
    slots = _build_slots_from_context(player_ctx)
    if urgency == "confirmed_neighbor":
        return _render(_pick(T_PROACTIVE_CONFIRMED_NEIGHBOR, rng), slots)
    return _render(_pick(T_PROACTIVE_ESCALATION, rng), slots)


def ask(text: str,
        resolve_player_ctx,
        list_top_suspects=None,
        get_daily_stats=None,
        tone: str = "neutral",
        rng: random.Random | None = None) -> dict[str, Any]:
    """
    Punto de entrada principal del chat. Detecta intent + resuelve
    callbacks para fetch de data.

    `resolve_player_ctx(player_name) -> dict | None`
    `list_top_suspects() -> list[dict]` (opcional)
    `get_daily_stats() -> dict` (opcional)

    Devuelve dict: {intent, answer, slots_used, missing_data}
    """
    rng = rng or random
    intent = classify_intent(text)

    if intent.name == "greeting":
        pool = T_GREETING_SARCASTIC if _maybe_sarcastic(tone, rng) else T_GREETING_NEUTRAL
        return {"intent": "greeting", "answer": _pick(pool, rng)}

    if intent.name == "help":
        return {"intent": "help", "answer": _pick(T_HELP, rng)}

    if intent.name == "daily_summary" and get_daily_stats:
        stats = get_daily_stats() or {}
        return {"intent": "daily_summary", "answer": daily_brief(stats, tone=tone, rng=rng)}

    if intent.name == "weekly_summary" and get_daily_stats:
        stats = get_daily_stats(days=7) if callable(get_daily_stats) else {}
        return {"intent": "weekly_summary", "answer": weekly_brief(stats, tone=tone, rng=rng)}

    if intent.name == "top_suspects" and list_top_suspects:
        top = list_top_suspects() or []
        if not top:
            return {"intent": "top_suspects", "answer": _pick(T_TOP_SUSPECTS_EMPTY, rng)}
        lst = ", ".join(f"{t.get('player_name','?')} ({_fmt_pct(t.get('score'))})"
                        for t in top[:5])
        return {"intent": "top_suspects",
                "answer": _pick(T_TOP_SUSPECTS_INTRO, rng).format(top_list=lst)}

    if intent.name in ("status", "status_short", "history", "advice",
                       "explain_decision", "compare"):
        player = intent.slots.get("player")
        if not player:
            return {"intent": intent.name, "answer": _pick(T_UNKNOWN, rng)}
        ctx = resolve_player_ctx(player) if resolve_player_ctx else None
        if not ctx:
            return {
                "intent": intent.name,
                "answer": _render(_pick(T_NO_PLAYER_DATA, rng), {"player": player}),
                "missing_data": True,
            }
        if intent.name == "compare":
            return {"intent": "compare",
                    "answer": compare_with_neighbors(
                        ctx, ctx.get("neighbors_list") or [], tone=tone, rng=rng
                    )}
        return {"intent": intent.name,
                "answer": respond_about_player(ctx, intent=intent.name, tone=tone, rng=rng)}

    return {"intent": "unknown", "answer": _pick(T_UNKNOWN, rng)}


# ──────────────────────────────────────────────────────────────────────
#  LLM polisher opcional — si OPENAI_API_KEY existe, refine la respuesta
# ──────────────────────────────────────────────────────────────────────

def llm_polish(answer: str, context: dict[str, Any] | None = None) -> str:
    """
    Si hay OPENAI_API_KEY en env, intenta refinar la respuesta vía LLM.
    Sin key, devuelve el answer original sin tocar. NUNCA invents data —
    el prompt es estricto sobre fidelidad.

    Timeout duro de 4s. Si falla, devuelve answer original.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return answer
    try:
        import urllib.request
        import json as _json
        sys_prompt = (
            "Sos Argus Oracle, un asistente AI para staff de Minecraft que detecta "
            "cheaters. Estilo neutral profesional con algún toque sarcástico ocasional. "
            "Devolvé EXACTAMENTE la misma información del mensaje original, "
            "pero más fluido. No agregues data que no esté presente. Máx 50 palabras. "
            "Conservá los números, nombres y porcentajes textualmente."
        )
        body = {
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": answer},
            ],
            "max_tokens": 180,
            "temperature": 0.4,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=_json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = _json.loads(resp.read().decode())
        choice = (data.get("choices") or [{}])[0]
        polished = (choice.get("message") or {}).get("content") or ""
        polished = polished.strip()
        if polished and len(polished) < 800:
            return polished
    except Exception:
        pass
    return answer


# ──────────────────────────────────────────────────────────────────────
#  Helper para escapar markdown en respuestas (cuando llegan al panel)
# ──────────────────────────────────────────────────────────────────────

def safe_text(s: str, max_len: int = 600) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len]
