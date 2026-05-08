package com.argus.scanner.core

/**
 * Modelos compartidos entre scanners. Mapea 1:1 con el JSON que espera el
 * backend Argus en POST /api/scans/<id>/results.
 */

data class ScanResult(
    val tipo: String,           // 'CHEAT_APP', 'ROOT_TOOL', 'LAUNCHER_FILE', etc.
    val categoria: String,      // 'CRITICAL', 'SOSPECHOSO', 'INFO'
    val nombre: String,
    val ruta: String,
    val descripcion: String,
    val confidence: Double,     // 0.0 – 1.0
    val alerta: String,         // 'CRITICAL' | 'SOSPECHOSO' | 'INFO'
    val detected_patterns: List<String> = emptyList(),
    val file_hash: String? = null,
)

sealed class ScanProgressEvent {
    data class Log(val line: String) : ScanProgressEvent()
    data class ScanCreated(val scanId: Long) : ScanProgressEvent()
    data class Done(val riskScore: Int, val verdict: String) : ScanProgressEvent()
    data class Failed(val message: String) : ScanProgressEvent()
}

/** Smart match con word boundaries (mismo concepto que smart_hack_match en
 *  el scanner desktop). Evita FP en "vertexshader" matcheando "vertex". */
fun smartHackMatch(text: String, term: String): Boolean {
    if (text.isEmpty() || term.isEmpty()) return false
    val t = text.lowercase()
    val tk = term.lowercase()
    val idx = t.indexOf(tk)
    if (idx < 0) return false
    val before = if (idx > 0) t[idx - 1] else null
    val after  = if (idx + tk.length < t.length) t[idx + tk.length] else null
    val isWord = { c: Char? -> c != null && (c.isLetterOrDigit()) }
    return !isWord(before) && !isWord(after)
}

/**
 * Bayesian-lite móvil — devuelve un multiplier para confidence ajustado
 * por la presencia de tokens NEG (apps casuales falsamente confundibles
 * con cheats) o POS (clientes/cheats inequívocos).
 *
 * Referencia: F#27 desktop. Adaptado al ecosistema móvil donde el
 * filename suele ser corto (label de app) y los tokens NEG son apps
 * casuales (Lawnchair, Tasker, AdAway).
 *
 * Output:
 *   1.0   neutro (no aplica)
 *   0.50  factor anti-FP fuerte (token NEG presente, sin POS)
 *   1.15  refuerzo (token POS presente)
 *
 * Si conviven NEG + POS, gana POS (cheats con disfraz no son comunes
 * en móvil; preferimos ser estrictos).
 */
fun bayesianLiteMultiplier(text: String): Double {
    if (text.isBlank()) return 1.0
    val lower = text.lowercase()
    val hasNeg = HackTerms.BAYES_NEGATIVE.any { lower.contains(it) }
    val hasPos = HackTerms.BAYES_POSITIVE.any { lower.contains(it) }
    return when {
        hasPos                 -> 1.15
        hasNeg && !hasPos      -> 0.50
        else                   -> 1.0
    }
}

/**
 * Aplica el multiplier al ScanResult. Si el resultado quedaría con
 * confidence < 0.35 lo degrada a SOSPECHOSO (de CRITICAL) o lo descarta
 * (de SOSPECHOSO). Devuelve null si el resultado debe descartarse por
 * el filtro Bayesian-lite móvil.
 */
fun applyBayesianFilter(r: ScanResult): ScanResult? {
    val text = "${r.nombre} ${r.ruta} ${r.descripcion}"
    val mult = bayesianLiteMultiplier(text)
    if (mult == 1.0) return r
    val newConf = (r.confidence * mult).coerceIn(0.0, 1.0)
    val newAlerta = when {
        r.alerta == "CRITICAL" && newConf < 0.55 -> "SOSPECHOSO"
        r.alerta == "SOSPECHOSO" && newConf < 0.35 -> return null
        else -> r.alerta
    }
    val newCat = if (newAlerta == "CRITICAL") "CRITICAL"
                 else if (newAlerta == "SOSPECHOSO") "SOSPECHOSO"
                 else r.categoria
    val patternTag = if (mult < 1.0) "bayes:fp_filter" else "bayes:reinforced"
    return r.copy(
        confidence = newConf,
        alerta = newAlerta,
        categoria = newCat,
        detected_patterns = r.detected_patterns + patternTag,
    )
}
