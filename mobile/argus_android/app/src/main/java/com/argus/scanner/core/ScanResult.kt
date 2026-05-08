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
