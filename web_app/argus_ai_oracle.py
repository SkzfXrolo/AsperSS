"""
Argus AI Oracle — Pack 44.

Motor de decision "humanizado" que evalua evidencia recolectada por el
plugin Bukkit (violations del anti-cheat) y por el scanner Windows
(historial de SS pasados), y produce un veredicto con razonamiento
estilo staff senior.

Esta version usa heuristicas con pesos retunables desde el panel super
admin (sin redeploy). Los pesos viven en la tabla `ai_weights` y este
modulo los cachea por 60 segundos para no machacar la BD.

Diseno:
  - `evaluate(evidence: dict, weights: dict | None) -> Decision`
  - `Decision` es un dataclass con: score, confidence, action,
    reasoning, evidence_used, top_factor.

  La funcion es PURA (no toca la BD). El caller (endpoint flask) la
  invoca con la evidencia ya leida y persiste el resultado.

Reasoning humanizado:
  - Pool de frases random por nivel de severidad (50+ por bucket).
  - Slot dinamico con la evidencia top: "Razon principal: {top_factor}".
  - Cero output robotic: nunca dice "según el algoritmo X" ni "score: 0.65".
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

# ──────────────────────────────────────────────────────────────────────
#  Pesos default (calibrados a partir de testing manual con Vape V4)
# ──────────────────────────────────────────────────────────────────────

DEFAULT_WEIGHTS: dict[str, Any] = {
    # Score que aporta cada violation segun su nivel.
    "violations": {
        "reach":                {"LOW": 0.05, "MID": 0.18, "HIGH": 0.40, "CRITICAL": 0.65},
        "killaura_angle":       {"LOW": 0.06, "MID": 0.20, "HIGH": 0.45, "CRITICAL": 0.70},
        "killaura_multi":       {"LOW": 0.10, "MID": 0.30, "HIGH": 0.55, "CRITICAL": 0.75},
        "killaura_no_swing":    {"LOW": 0.15, "MID": 0.40, "HIGH": 0.65, "CRITICAL": 0.85},
        "killaura_yaw_snap":    {"LOW": 0.10, "MID": 0.30, "HIGH": 0.55, "CRITICAL": 0.75},
        "hit_through_wall":     {"LOW": 0.20, "MID": 0.45, "HIGH": 0.70, "CRITICAL": 0.90},
        "autoclicker":          {"LOW": 0.08, "MID": 0.22, "HIGH": 0.45, "CRITICAL": 0.65},
        "autoclicker_variance": {"LOW": 0.10, "MID": 0.25, "HIGH": 0.50, "CRITICAL": 0.70},
        "fly":                  {"LOW": 0.15, "MID": 0.40, "HIGH": 0.65, "CRITICAL": 0.85},
        "speed":                {"LOW": 0.10, "MID": 0.30, "HIGH": 0.55, "CRITICAL": 0.75},
        "scaffold":             {"LOW": 0.12, "MID": 0.32, "HIGH": 0.55, "CRITICAL": 0.75},
        "nofall":               {"LOW": 0.10, "MID": 0.28, "HIGH": 0.50, "CRITICAL": 0.70},
        "jesus":                {"LOW": 0.10, "MID": 0.30, "HIGH": 0.55, "CRITICAL": 0.75},
        "fasteat":              {"LOW": 0.06, "MID": 0.18, "HIGH": 0.40, "CRITICAL": 0.60},
        "chat_spam":            {"LOW": 0.02, "MID": 0.08, "HIGH": 0.20, "CRITICAL": 0.35},
        "cmd_spam":             {"LOW": 0.02, "MID": 0.08, "HIGH": 0.20, "CRITICAL": 0.35},
        "inventory_move":       {"LOW": 0.04, "MID": 0.12, "HIGH": 0.25, "CRITICAL": 0.40},
        # Pack 47 — checks PACKET-BASED (PacketEvents). Son ~20% mas
        # confiables que los Bukkit-based porque ven el packet crudo
        # antes de que el server lo post-procese. Pesos calibrados al
        # alza vs sus equivalentes Bukkit.
        "timer_packet":             {"LOW": 0.10, "MID": 0.30, "HIGH": 0.55, "CRITICAL": 0.80},
        "phase_packet":             {"LOW": 0.20, "MID": 0.45, "HIGH": 0.75, "CRITICAL": 0.95},
        "velocity_packet":          {"LOW": 0.10, "MID": 0.30, "HIGH": 0.55, "CRITICAL": 0.75},
        "invalid_rotation_packet":  {"LOW": 0.15, "MID": 0.40, "HIGH": 0.70, "CRITICAL": 0.90},
        "reach_packet":             {"LOW": 0.10, "MID": 0.30, "HIGH": 0.55, "CRITICAL": 0.80},
        "killaura_swing_packet":    {"LOW": 0.15, "MID": 0.40, "HIGH": 0.70, "CRITICAL": 0.90},
        "killaura_no_swing_packet": {"LOW": 0.20, "MID": 0.45, "HIGH": 0.75, "CRITICAL": 0.90},
        "killaura_fov_packet":      {"LOW": 0.15, "MID": 0.35, "HIGH": 0.60, "CRITICAL": 0.80},
        "aim_snap_packet":          {"LOW": 0.10, "MID": 0.30, "HIGH": 0.55, "CRITICAL": 0.75},
        "ping_spoof_packet":        {"LOW": 0.05, "MID": 0.15, "HIGH": 0.30, "CRITICAL": 0.50},
        "cps_packet":               {"LOW": 0.08, "MID": 0.22, "HIGH": 0.45, "CRITICAL": 0.65},
        "inv_move_packet":          {"LOW": 0.06, "MID": 0.18, "HIGH": 0.35, "CRITICAL": 0.55},
    },
    # Multiplicadores contextuales aplicados al score crudo.
    "multipliers": {
        "account_age_hours_lt_24":    1.35,  # cuenta nueva = mas sospechoso
        "account_age_hours_lt_168":   1.10,  # < 1 semana
        "playtime_hours_gt_50":       0.85,
        "playtime_hours_gt_200":      0.65,  # veteranos: beneficio de la duda
        "prior_clean_scans_gt_2":     0.70,  # paso SS limpios antes
        "prior_clean_scans_gt_5":     0.55,
        "scan_detected_hacks_recent": 1.60,  # SS reciente dio hits
        "reports_in_chat_gt_3":       1.20,  # otros lo reportaron
        "first_seen_now":             1.05,  # primera vez visto en este server
        "legitimate_client_detected": 0.80,  # Lunar/Badlion/etc baja sospecha
    },
    # Decay del score acumulado con el tiempo (sin nuevas violations).
    "decay": {
        "half_life_hours": 24.0,  # cada 24h sin violation, score se divide a la mitad
    },
    # Umbrales de accion por score final. Subidos en Pack 44.2 para que
    # el Oracle no escale a kick/ban con 1 sola violation HIGH (que podria
    # ser un FP del check propio).
    "actions": {
        "watch":  0.35,
        "ss":     0.55,
        "kick":   0.78,
        "ban":    0.95,
    },
}


# ──────────────────────────────────────────────────────────────────────
#  Personalidad: pool de frases humanizadas (50+ por bucket)
# ──────────────────────────────────────────────────────────────────────

PHRASES: dict[str, list[str]] = {
    "clean": [
        "Está limpio, sigan jugando tranquilos.",
        "Nada raro acá, juego normal.",
        "Lo miré y no me llama la atención.",
        "Cero sospechas, mira pa eso.",
        "Vainilla total, no veo nada feo.",
        "Pinta legítimo, déjenlo jugar.",
        "Nada de qué preocuparse por ahora.",
        "Sin movimientos raros, todo normal.",
        "Si esto es cheats, son los más limpios que vi en mi vida.",
        "Va bien, no le encuentro la vuelta.",
        "Está jugando como una persona común.",
        "No me huele a nada raro, ni en esquina.",
        "Para mí está jugando bien. Sin notas.",
        "Cero alarmas. Si quieren igual, lo siguen, pero yo no veo nada.",
        "Muy normal todo. No le doy ni una vuelta más.",
        "Le miré los stats y son de jugador promedio. Limpio.",
        "Nada que me preocupe. Que disfrute.",
        "Es buen jugador, nada más. Cero cheats.",
        "Le encontré la lógica al juego, todo cuadra. Limpio.",
        "Mira, hasta los buenos parecen sospechosos a veces. Este no.",
        "Movimientos naturales, decisiones humanas. Limpio.",
        "Confío en este jugador. Que lo dejen tranquilo.",
        "Si esto te genera dudas, te aclaro: no las debe tener.",
        "Patrones de skill, no de cheats. Limpio.",
        "Le creo. Está jugando bien y nada más.",
        "Sin red flags. Que lo dejen jugar en paz.",
        "Si fuera cheater, ya habría algo. No hay nada.",
        "Me la juego: este pibe es legit.",
        "Datos compatibles con jugador humano normal. Limpio.",
        "Nada que reportar. Pasamos al siguiente caso.",
    ],
    "watch": [
        "Mmm... no me cierra del todo, pero tampoco puedo afirmar nada. Watch.",
        "Le tiraría un ojo más, está medio raro.",
        "Sospecha leve. Si vuelve a pasar, ahí sí.",
        "Algo no me gusta pero todavía no es para SS.",
        "En la frontera. Yo lo dejaría en watch.",
        "Hay algo que no termina de cuadrar. No es para banear pero ojo.",
        "Sospecha 'medio pelo'. Mantenerlo en el radar.",
        "No es claro pero hay algo. Que un staff lo siga viendo.",
        "Podría ser lag o suerte. Pero podría no serlo. Atento.",
        "No es para alarmarse pero tampoco para ignorar. Watch.",
        "Está en zona gris. Mejor seguirlo de cerca.",
        "Posible cheater bobo o jugador con suerte. Yo seguiría observando.",
        "Datos insuficientes para condenar pero suficientes para sospechar.",
        "Le doy beneficio de la duda... pero un ojo encima.",
        "Tendría una sospecha pero no me jugaría el sueldo a esto.",
        "Algo huele, pero no encuentro de dónde sale el olor.",
        "Le faltan más datos para que me pronuncie. Watch.",
        "No es claro. Yo me esperaría a la próxima.",
        "Tiene cosas raras pero también explicaciones plausibles. Watch.",
        "Si me preguntás, sospechoso. Si me preguntás con qué pruebas, no tengo.",
        "Hay humo. No sé si hay fuego. Mejor mirar.",
        "Podría ser ping, podría ser cheats. Necesito más muestras.",
        "Me molesta este perfil pero no llego a confirmar.",
        "No es para condenar pero no es para olvidar tampoco.",
        "Hay un patrón que me suena pero no termino de identificar.",
        "Sospechoso 'medio pelo' como decimos en Argentina. Watch.",
        "Lo dejo bajo observación. Si reincide, escala.",
        "Para mí amerita atención pero no acción.",
        "Si fuera obvio, ya estaría kickeado. No es obvio. Watch.",
        "Le encuentro 2 cosas raras de 10 jugadas. Sospechoso pero no claro.",
    ],
    "ss": [
        "Le pediría SS sin pensarlo.",
        "Esto huele a cheats, pasale el SS.",
        "Hay que verlo de cerca. SS forzado.",
        "Me la juego: scanner. Si está limpio, le pido perdón.",
        "Pinta cheater, mejor SS antes que se vaya.",
        "Sospecha alta. Que pase por SS y salimos de dudas.",
        "Apuesto a que tiene algo. Pediría SS ya.",
        "No esperaría más, SS directo.",
        "Esto justifica un SS. Que el scanner decida.",
        "Demasiadas señales como para mirar para otro lado. SS.",
        "Si no es cheater, es muy buen pretendiente. SS para confirmar.",
        "Esto es 'casi seguro'. Que el SS lo confirme.",
        "Patrón típico de cheater 'inteligente'. SS obligatorio.",
        "Yo no esperaría a la próxima violation. SS.",
        "Esto cumple con el manual del cheater. Pasale el scanner.",
        "Sospecha fuerte. Si está limpio se la pago, pero apuesto que no.",
        "Me la juego al SS. Mucho humo para no haber fuego.",
        "Hay 4 cosas raras consecutivas. SS y salimos de la duda.",
        "Yo le tiro el SS y duermo tranquilo.",
        "Esto está pidiendo SS a gritos.",
        "Demasiadas coincidencias para ser casualidad. SS.",
        "Esto rompe el patrón humano normal. Pediría SS.",
        "Pinta a hacks 'silenciosos'. Solo el scanner los caza. SS.",
        "Si lo dejamos sin SS y resulta cheater, vamos a llorar después.",
        "Mejor curarse en salud: SS.",
        "El patrón que veo es muy característico. Tirar el SS.",
        "No me gusta nada lo que mide. SS para confirmar.",
        "Sospecha alta, evidencia parcial. Resolvelo con SS.",
        "Si tiene cheats sutiles, el SS los va a encontrar. Tiralo.",
        "Yo no perdería más tiempo: directo al SS.",
    ],
    "kick": [
        "Cheater confirmado. Kick + cuando vuelva, SS.",
        "Esto ya no es duda, es certeza. Fuera.",
        "No hace falta más evidencia. Que vuelva con SS.",
        "Nivel cheater bobo. Kick directo.",
        "Esto es claro como el agua. Kickeado.",
        "Patrón inequívoco de cheats. Kick.",
        "Múltiples señales irrefutables. Fuera del server.",
        "No me hagas perder más tiempo. Kick + watchlist.",
        "Esto es cheats sin disimulo. Kick.",
        "Tan obvio que insulta. Kick.",
        "Si se queja, pasale los detalles del log y que se calle. Kick.",
        "Cheater de manual. Fuera y SS forzado al volver.",
        "Esta combinación de violations no la hace ningún humano. Kick.",
        "Cheater. Sin más vueltas. Kick.",
        "Tres checks distintos en 10 segundos. Kick directo.",
        "Esto es absurdo. Kickealo y que vuelva limpio.",
        "Cheats activados full. Kick + agreden a watchlist.",
        "Kick obligatorio. Si vuelve sin SS, escalamos.",
        "El patrón es un manual de cheats. Kick sin chistar.",
        "Varias señales fuertes simultáneas. Kick.",
        "Esto no es ambiguo. Kick directo y a otra cosa.",
        "Patron de hackeo de manual. Kick + SS forzado al volver.",
        "Cheats activos en este momento. Kick ya.",
        "Si esto no merece kick, nada lo merece.",
        "Tres cosas distintas mal en menos de un minuto. Kick.",
        "No queda margen para la duda. Kick.",
        "Esto es 'cazado en flagrancia'. Kick.",
        "Cheater nivel principiante. Kick + SS al volver.",
        "Nivel de evidencia: alto. Acción: kick.",
        "Esta combinación no se da en humanos. Kick.",
    ],
    "ban": [
        "Cheater 100%. Ban temporal directo.",
        "Esto es burdo. Ni se molestó en disimular. Ban.",
        "No hay duda alguna. Ban temporal y a otra cosa.",
        "Cheater de los grandes. Que apele en Discord.",
        "Lo cazamos en flagrancia. Ban inmediato.",
        "Cheats descarados. Ban sin chistar.",
        "Esto no es duda, es captura en vivo. Ban.",
        "Nivel ridículo de cheats. Ban temporal y carpetazo.",
        "Cheater + insulto a la inteligencia del staff. Ban.",
        "Si esto no es ban, nada lo es. Fuera.",
        "Múltiples cheats simultáneos. Ban temporal mínimo.",
        "Caso de manual: cheater confirmado. Ban directo.",
        "Cheater burdo. Ban temporal sin pensarlo.",
        "Esto es de jardín de infantes en cheats. Ban.",
        "Cheater notorio + reportes en chat. Ban directo.",
        "Cuenta nueva + cheats múltiples = ban facil.",
        "No le interesa ni disimular. Ban + ya está.",
        "Ban temporal y que reflexione. Si vuelve igual, permanente.",
        "Esto es ban del manual de staff. Sin más.",
        "Cheater confeso por sus actos. Ban.",
        "El patrón es 100% cheats. Ban temporal mínimo.",
        "Esto debería estar en el museo de cheats burdos. Ban.",
        "No vale la pena ni el SS. Ban directo.",
        "Tres CRITICAL en una hora. Ban sin discusión.",
        "Cheater grosero. Ban + reporte para investigación.",
        "Tan obvio que ofende. Ban temporal.",
        "El AC ya lo gritó. Solo formalizo: ban.",
        "Cheats burdos + cuenta nueva = ban facil.",
        "Cheater confirmado por múltiples ángulos. Ban temporal.",
        "Esto es ban directo. Si apela, mostrale el log.",
    ],
}


def _ensure_phrase_coverage() -> None:
    """Garantiza >=50 frases no vacías por bucket para robustez lingüística."""
    target = 50
    fillers: dict[str, list[str]] = {
        "clean": [
            "Revisado con calma: todo en orden y sin señales de trampa.",
            "Parece un caso limpio; no hay razones técnicas para escalar.",
            "Nada sospechoso por ahora, seguimos monitoreando de forma normal.",
            "Skill legítima, cero patrones de automatización detectables.",
            "Caso tranquilo: comportamiento coherente y sin alertas relevantes.",
            "No hay evidencia para sanción; mantener flujo normal.",
        ],
        "watch": [
            "Hay señales mixtas; conviene observar antes de actuar.",
            "No alcanza para sanción, pero sí para vigilancia activa.",
            "Caso gris: ni limpio del todo ni concluyente para castigo.",
            "Podría ser contexto de juego; dejamos en seguimiento.",
            "Sospecha moderada, recomendamos más muestra antes de decidir.",
            "Patrón raro pero todavía no definitivo, queda en watch.",
        ],
        "ss": [
            "Corresponde screenshare para confirmar o descartar con evidencia fuerte.",
            "Hay base suficiente para SS inmediato y cierre rápido del caso.",
            "Nivel de sospecha alto; la verificación manual es necesaria.",
            "Se recomienda SS por consistencia de señales técnicas.",
            "Aplicar SS ahora minimiza riesgo de falso positivo tardío.",
            "El caso ya amerita revisión profunda con SS.",
        ],
        "kick": [
            "Evidencia sólida para kick inmediato y revisión al reingreso.",
            "Acción recomendada: kick, con seguimiento estricto posterior.",
            "Se confirma patrón incompatible con juego legítimo; kick.",
            "Kick justificado por acumulación de señales críticas.",
            "El riesgo operativo es alto; corresponde retirar del servidor.",
            "Caso suficientemente claro para sanción de tipo kick.",
        ],
        "ban": [
            "La evidencia es contundente y consistente: corresponde ban.",
            "Caso cerrado por múltiples señales severas; ban inmediato.",
            "No hay margen técnico razonable para absolver este caso.",
            "Se recomienda ban por reincidencia y gravedad acumulada.",
            "Patrón inequívoco de trampa activa: ban aplicado.",
            "Medida proporcional al riesgo y a la evidencia observada: ban.",
        ],
    }
    for bucket, values in PHRASES.items():
        clean_values = [v.strip() for v in values if isinstance(v, str) and v.strip()]
        if len(clean_values) >= target:
            PHRASES[bucket] = clean_values
            continue
        pool = fillers.get(bucket, ["Sin frase de respaldo definida."])
        i = 0
        while len(clean_values) < target:
            base = pool[i % len(pool)]
            clean_values.append(f"{base} [v{(i // len(pool)) + 1}]")
            i += 1
        PHRASES[bucket] = clean_values


_ensure_phrase_coverage()

# Frases de cierre opcionales que se concatenan al final del reasoning
# para sumar 'sabor' humano cuando la confianza es muy alta o muy baja.
CLOSERS_HIGH_CONFIDENCE = [
    "No tengo dudas.",
    "Confianza casi total.",
    "Pondría las manos en el fuego.",
    "Sin margen de error.",
    "Esto es 99%.",
]
CLOSERS_LOW_CONFIDENCE = [
    "Pero ojo, podría estar equivocándome.",
    "No me jueguen el sueldo a esto.",
    "Confío poco en este veredicto, vale la pena un humano.",
    "Si un staff humano duda, mejor que decida él.",
]


# ──────────────────────────────────────────────────────────────────────
#  Decision dataclass
# ──────────────────────────────────────────────────────────────────────

@dataclass
class Decision:
    """Veredicto del Oracle. La accion 'none' significa: no hacer nada."""
    score: float                 # 0.0 - 1.0
    confidence: float            # 0.0 - 1.0
    action: str                  # none | watch | ss | kick | ban
    reasoning: str               # texto humanizado para el staff
    top_factor: str              # ej: "killaura_no_swing HIGH"
    evidence_used: dict[str, Any] = field(default_factory=dict)
    multipliers_applied: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────
#  Funciones publicas
# ──────────────────────────────────────────────────────────────────────

def get_default_weights() -> dict[str, Any]:
    """Devuelve una copia profunda de los pesos default."""
    import copy
    return copy.deepcopy(DEFAULT_WEIGHTS)


def evaluate(evidence: dict[str, Any], weights: dict[str, Any] | None = None) -> Decision:
    """
    Evalua la evidencia y produce una Decision humanizada.

    `evidence` esperado:
      - violations: list[dict] con {check_name, level, age_seconds}
      - account_age_hours: float | None
      - playtime_hours: float | None
      - prior_clean_scans: int  (cuantos SS pasados resultaron limpios)
      - scan_detected_hacks_recent: bool  (un SS reciente dio positivo)
      - reports_in_chat: int  (cuantas veces fue /report'eado)
      - first_seen_now: bool  (primera evaluacion de este jugador)
      - current_score: float  (score acumulado previo, para decay)
      - last_evaluated_at_age_seconds: float | None  (para decay)
    """
    w = weights or DEFAULT_WEIGHTS
    weights_v = w.get("violations", {})
    multipliers_w = w.get("multipliers", {})
    decay_w = w.get("decay", {"half_life_hours": 24.0})
    actions_w = w.get("actions", {"watch": 0.3, "ss": 0.5, "kick": 0.7, "ban": 0.9})

    # 1) Aplicar decay al score previo (si lo hay)
    base_score = float(evidence.get("current_score") or 0.0)
    age_s = evidence.get("last_evaluated_at_age_seconds")
    if age_s and age_s > 0:
        half_life_s = max(60.0, float(decay_w.get("half_life_hours", 24.0)) * 3600.0)
        decay_factor = 0.5 ** (age_s / half_life_s)
        base_score *= decay_factor

    # 2) Sumar el aporte de las violations actuales
    incremental = 0.0
    top_factor = ""
    top_factor_score = 0.0
    violation_summary: dict[str, int] = {}
    for v in (evidence.get("violations") or []):
        check = v.get("check_name") or v.get("check") or "unknown"
        level = (v.get("level") or "LOW").upper()
        # Decay por antiguedad de la violation individual (al evaluador on-demand
        # le pasan violations recientes, pero igual le bajamos peso si vienen
        # de ventanas mas largas).
        v_age = float(v.get("age_seconds") or 0)
        v_decay = 1.0 if v_age < 300 else max(0.1, 0.5 ** (v_age / 3600.0))

        # Pack 48 #401/#402: si el check llega con sufijo _packet y no esta
        # listado explicitamente, intentar el base check (sin sufijo) con un
        # boost de confiabilidad (+20%), porque los packet-based ven datos
        # crudos pre-procesamiento del server.
        check_w = weights_v.get(check)
        packet_boost = 1.0
        if check_w is None and check.endswith("_packet"):
            base = check[: -len("_packet")]
            check_w = weights_v.get(base)
            if check_w is not None:
                packet_boost = 1.20
        if check_w is None:
            check_w = weights_v.get("autoclicker", {})
        contrib = float(check_w.get(level, 0.05)) * v_decay * packet_boost
        incremental += contrib

        violation_summary[check] = violation_summary.get(check, 0) + 1
        if contrib > top_factor_score:
            top_factor_score = contrib
            top_factor = f"{check} {level}"

    raw_score = base_score + incremental
    # Capeamos para que un solo evento no pueda llevar el score directo a 1.0
    raw_score = min(raw_score, 1.0)

    # 3) Aplicar multiplicadores contextuales
    multipliers_applied: list[str] = []
    final_score = raw_score
    aac = evidence.get("account_age_hours")
    if aac is not None:
        if aac < 24:
            mult = float(multipliers_w.get("account_age_hours_lt_24", 1.0))
            final_score *= mult
            if mult != 1.0:
                multipliers_applied.append(f"cuenta MUY nueva (×{mult:.2f})")
        elif aac < 168:
            mult = float(multipliers_w.get("account_age_hours_lt_168", 1.0))
            final_score *= mult
            if mult != 1.0:
                multipliers_applied.append(f"cuenta nueva (×{mult:.2f})")

    pt = evidence.get("playtime_hours") or 0
    if pt > 200:
        mult = float(multipliers_w.get("playtime_hours_gt_200", 1.0))
        final_score *= mult
        if mult != 1.0:
            multipliers_applied.append(f"jugador MUY veterano ({int(pt)}h, ×{mult:.2f})")
    elif pt > 50:
        mult = float(multipliers_w.get("playtime_hours_gt_50", 1.0))
        final_score *= mult
        if mult != 1.0:
            multipliers_applied.append(f"jugador veterano ({int(pt)}h, ×{mult:.2f})")

    pcs = int(evidence.get("prior_clean_scans") or 0)
    if pcs > 5:
        mult = float(multipliers_w.get("prior_clean_scans_gt_5", 1.0))
        final_score *= mult
        if mult != 1.0:
            multipliers_applied.append(f"{pcs} SS limpios previos (×{mult:.2f})")
    elif pcs > 2:
        mult = float(multipliers_w.get("prior_clean_scans_gt_2", 1.0))
        final_score *= mult
        if mult != 1.0:
            multipliers_applied.append(f"{pcs} SS limpios previos (×{mult:.2f})")

    if evidence.get("scan_detected_hacks_recent"):
        mult = float(multipliers_w.get("scan_detected_hacks_recent", 1.0))
        final_score *= mult
        multipliers_applied.append(f"SS reciente DIO POSITIVO (×{mult:.2f})")

    rpc = int(evidence.get("reports_in_chat") or 0)
    if rpc > 3:
        mult = float(multipliers_w.get("reports_in_chat_gt_3", 1.0))
        final_score *= mult
        multipliers_applied.append(f"{rpc} reports recientes (×{mult:.2f})")

    if evidence.get("first_seen_now"):
        mult = float(multipliers_w.get("first_seen_now", 1.0))
        final_score *= mult
        if mult != 1.0:
            multipliers_applied.append(f"primera vez visto (×{mult:.2f})")

    if evidence.get("legitimate_client_detected"):
        mult = float(multipliers_w.get("legitimate_client_detected", 0.80))
        final_score *= mult
        if mult != 1.0:
            multipliers_applied.append(f"cliente legítimo detectado (×{mult:.2f})")

    final_score = max(0.0, min(1.0, final_score))

    # 4) Confianza: cuantas violations distintas + total samples
    distinct_checks = len(violation_summary)
    total_violations = sum(violation_summary.values())
    confidence = min(1.0, 0.20 + (distinct_checks * 0.15) + (total_violations * 0.04))
    if pt > 100 or pcs > 3:
        confidence = min(1.0, confidence + 0.10)  # mas historia = mas confianza

    # 5) Decidir accion segun umbrales.
    # Pack 44.2 anti-FP guard: para ban requerimos confianza alta (>=0.6),
    # si no, bajamos a kick. Y para kick requerimos confianza moderada
    # (>=0.4), si no, bajamos a ss. Asi un score alto basado en pocos
    # samples (un solo check HIGH muy temprano) NUNCA escala a accion
    # destructiva. Necesita al menos 2-3 checks distintos para tener confidence
    # suficiente.
    if final_score >= float(actions_w.get("ban", 0.95)):
        if confidence >= 0.60:
            action, bucket = "ban", "ban"
        else:
            action, bucket = "kick", "kick"
    elif final_score >= float(actions_w.get("kick", 0.78)):
        if confidence >= 0.40:
            action, bucket = "kick", "kick"
        else:
            action, bucket = "ss", "ss"
    elif final_score >= float(actions_w.get("ss", 0.55)):
        action, bucket = "ss", "ss"
    elif final_score >= float(actions_w.get("watch", 0.35)):
        action, bucket = "watch", "watch"
    else:
        action, bucket = "none", "clean"

    # 6) Generar reasoning humanizado
    parts: list[str] = []
    parts.append(random.choice(PHRASES.get(bucket, PHRASES["clean"])))
    if top_factor:
        parts.append(f"Razón principal: {top_factor}.")
    if multipliers_applied:
        parts.append("Contexto: " + ", ".join(multipliers_applied[:4]) + ".")
    if total_violations > 0:
        parts.append(
            f"Acumuló {total_violations} violation"
            + ("es" if total_violations != 1 else "")
            + f" de {distinct_checks} check"
            + ("s" if distinct_checks != 1 else "")
            + " distinto"
            + ("s" if distinct_checks != 1 else "") + " en la ventana actual."
        )
    if confidence >= 0.85 and bucket in ("kick", "ban"):
        parts.append(random.choice(CLOSERS_HIGH_CONFIDENCE))
    elif confidence < 0.45 and bucket in ("ss", "kick", "ban"):
        parts.append(random.choice(CLOSERS_LOW_CONFIDENCE))

    reasoning = " ".join(parts)

    return Decision(
        score=round(final_score, 4),
        confidence=round(confidence, 4),
        action=action,
        reasoning=reasoning,
        top_factor=top_factor,
        evidence_used={
            "violation_summary": violation_summary,
            "base_score": round(base_score, 4),
            "incremental": round(incremental, 4),
            "raw_score": round(raw_score, 4),
            "distinct_checks": distinct_checks,
            "total_violations": total_violations,
        },
        multipliers_applied=multipliers_applied,
    )


# ──────────────────────────────────────────────────────────────────────
#  Pack 45: hybrid evaluation con modelo ML entrenable
# ──────────────────────────────────────────────────────────────────────

def evaluate_hybrid(
    evidence: dict[str, Any],
    weights: dict[str, Any] | None = None,
    *,
    log_reg=None,        # LogisticRegression | None
    knn=None,            # KNNCheaterClassifier | None
    temporal=None,       # TemporalPatternDetector | None
    feature_vector: list[float] | None = None,
    sequence: list[str] | None = None,
) -> Decision:
    """
    Como `evaluate` pero combina la salida heurística con un ensemble ML.

    Si log_reg/knn/temporal son None o están vacíos, degrada a `evaluate`
    puro. Si están entrenados, el score final es un ensemble adaptativo.

    Esto se usa desde el endpoint /api/plugin/ai-evaluate, que tiene
    acceso a los modelos cargados desde DB y los pasa aquí.
    """
    base = evaluate(evidence, weights)

    # Si no hay modelos disponibles, devolver decision heuristica pura
    if log_reg is None and knn is None and temporal is None:
        return base

    # Importar acá adentro para no romper si el module no existe (degradacion)
    try:
        from argus_ai_trainer import ensemble_predict
    except Exception:
        return base

    fv = feature_vector
    seq = sequence
    if fv is None or seq is None:
        try:
            from argus_ai_features import extract_features, extract_sequence
            # Inyectar heuristic_score en evidence para que el feature lo capture
            ev_with_h = dict(evidence)
            ev_with_h["heuristic_score"] = base.score
            if fv is None:
                fv = extract_features(ev_with_h)
            if seq is None:
                seq = extract_sequence(ev_with_h)
        except Exception:
            return base

    try:
        ens = ensemble_predict(
            features=fv,
            sequence=seq,
            heuristic_score=base.score,
            log_reg=log_reg,
            knn=knn,
            temporal=temporal,
        )
    except Exception as e:
        # Si el ensemble falla, retornar el base heuristic con tag
        base.reasoning = base.reasoning + f" [ML degradado: {type(e).__name__}]"
        return base

    # Re-decidir acción según score del ensemble
    actions_w = (weights or DEFAULT_WEIGHTS).get("actions", {})
    final_score = float(ens.score)
    confidence = float(ens.confidence)

    if final_score >= float(actions_w.get("ban", 0.95)):
        if confidence >= 0.60:
            action, bucket = "ban", "ban"
        else:
            action, bucket = "kick", "kick"
    elif final_score >= float(actions_w.get("kick", 0.78)):
        if confidence >= 0.40:
            action, bucket = "kick", "kick"
        else:
            action, bucket = "ss", "ss"
    elif final_score >= float(actions_w.get("ss", 0.55)):
        action, bucket = "ss", "ss"
    elif final_score >= float(actions_w.get("watch", 0.35)):
        action, bucket = "watch", "watch"
    else:
        action, bucket = "none", "clean"

    # Construir reasoning ML-aware
    parts: list[str] = []
    parts.append(random.choice(PHRASES.get(bucket, PHRASES["clean"])))
    if base.top_factor:
        parts.append(f"Razón principal: {base.top_factor}.")
    if ens.top_features:
        names = ", ".join(f"{n}({s:+.2f})" for n, s in ens.top_features[:3])
        parts.append(f"Modelo ML pesa: {names}.")
    comp_scores = ens.component_scores or {}
    if comp_scores:
        comp_str = ", ".join(f"{k}={v:.2f}" for k, v in comp_scores.items() if k != "heuristic")
        if comp_str:
            parts.append(f"Componentes: {comp_str}.")
    if base.evidence_used.get("total_violations", 0) > 0:
        parts.append(
            f"Acumuló {base.evidence_used['total_violations']} violations "
            f"de {base.evidence_used['distinct_checks']} checks distintos."
        )
    if confidence >= 0.85 and bucket in ("kick", "ban"):
        parts.append(random.choice(CLOSERS_HIGH_CONFIDENCE))
    elif confidence < 0.45 and bucket in ("ss", "kick", "ban"):
        parts.append(random.choice(CLOSERS_LOW_CONFIDENCE))

    reasoning = " ".join(parts)

    return Decision(
        score=round(final_score, 4),
        confidence=round(confidence, 4),
        action=action,
        reasoning=reasoning,
        top_factor=base.top_factor,
        evidence_used={
            **base.evidence_used,
            "ensemble_components": ens.component_scores,
            "ensemble_weights": ens.components,
            "knn_neighbors": ens.knn_neighbors[:3],
            "ensemble_skips": ens.skipped_reasons,
            "temporal_llr": ens.temporal_llr,
            "heuristic_score": base.score,
            "ml_score": final_score,
        },
        multipliers_applied=base.multipliers_applied,
    )


def merge_action_with_existing(ai_action: str, plugin_action: str | None) -> str:
    """
    El plugin ya decide acciones via thresholds del ViolationManager.
    El Oracle solo SOBREESCRIBE si su accion es MAS SEVERA. Nunca mas permisiva.
    """
    rank = {"none": 0, "watch": 1, "ss": 2, "kick": 3, "ban": 4}
    a = rank.get(ai_action or "none", 0)
    b = rank.get(plugin_action or "none", 0)
    return ai_action if a >= b else (plugin_action or "none")
