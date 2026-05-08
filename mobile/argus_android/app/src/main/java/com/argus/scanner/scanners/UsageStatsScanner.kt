package com.argus.scanner.scanners

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.os.Build
import android.os.Process
import com.argus.scanner.core.HackTerms
import com.argus.scanner.core.ScanResult
import com.argus.scanner.core.smartHackMatch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit

/**
 * UsageStatsScanner — item Android #4 (equivalente del Prefetch desktop).
 *
 * Combina dos APIs:
 *  - UsageStatsManager.queryUsageStats(INTERVAL_DAILY, hace 30d, ahora) →
 *    listado agregado por package: totalTimeInForeground + lastTimeUsed.
 *  - UsageStatsManager.queryEvents(...) → granular: cada ACTIVITY_RESUMED
 *    con timestamp. Permite ver "Toolbox lanzado 14 veces hoy".
 *
 * Reporta como CRITICAL si el package es de la blacklist BEDROCK_CHEAT,
 * MEMORY_EDITOR o ROOT_MANAGER y fue ABIERTO en los últimos 30 días
 * (no basta con que esté instalado: si lo lanzó implica intención).
 *
 * Reporta como SOSPECHOSO si un package match heurístico por label
 * (HACK_TERMS) y fue lanzado.
 *
 * Reporta como INFO el último launch de Minecraft Bedrock/Pojav (contexto
 * para el panel: "vino cheateando ahora mismo o hace 3 días?").
 *
 * Permiso requerido: PACKAGE_USAGE_STATS (special — concedido en
 * Settings > Apps > Special access > Usage access).
 * Si no lo tiene, retorna empty list silenciosamente con log.
 */
class UsageStatsScanner(private val ctx: Context) {

    fun hasPermission(): Boolean {
        val ops = ctx.getSystemService(Context.APP_OPS_SERVICE) as? AppOpsManager
            ?: return false
        val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ops.unsafeCheckOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(), ctx.packageName
            )
        } else {
            @Suppress("DEPRECATION")
            ops.checkOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(), ctx.packageName
            )
        }
        return mode == AppOpsManager.MODE_ALLOWED
    }

    fun scan(): List<ScanResult> {
        if (!hasPermission()) return emptyList()
        val usm = ctx.getSystemService(Context.USAGE_STATS_SERVICE) as? UsageStatsManager
            ?: return emptyList()

        val now    = System.currentTimeMillis()
        val window = TimeUnit.DAYS.toMillis(30)
        val begin  = now - window

        // 1) Buckets agregados — mapa pkg → último uso ms.
        val lastUsedByPkg = mutableMapOf<String, Long>()
        val totalTimeByPkg = mutableMapOf<String, Long>()
        try {
            val stats = usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, begin, now)
                ?: emptyList()
            for (us in stats) {
                // UsageStats.packageName en compileSdk 34 es String? (Java
                // getter, no smart-castea como property). Capturamos a local.
                val pkg = us.packageName ?: continue
                if (pkg.isBlank()) continue
                val prev = lastUsedByPkg[pkg] ?: 0L
                if (us.lastTimeUsed > prev) lastUsedByPkg[pkg] = us.lastTimeUsed
                totalTimeByPkg.merge(pkg, us.totalTimeInForeground) { a, b -> a + b }
            }
        } catch (_: Exception) { /* devuelve vacío silencioso */ }

        // 2) Conteo de launches por queryEvents (ACTIVITY_RESUMED).
        val launchCountByPkg = mutableMapOf<String, Int>()
        try {
            val events = usm.queryEvents(begin, now)
            val ev = UsageEvents.Event()
            while (events.hasNextEvent()) {
                events.getNextEvent(ev)
                if (ev.eventType == UsageEvents.Event.ACTIVITY_RESUMED ||
                    ev.eventType == UsageEvents.Event.MOVE_TO_FOREGROUND) {
                    val pkg = ev.packageName ?: continue
                    launchCountByPkg.merge(pkg, 1) { a, _ -> a + 1 }
                }
            }
        } catch (_: Exception) { /* no fatal */ }

        if (lastUsedByPkg.isEmpty() && launchCountByPkg.isEmpty()) return emptyList()

        val out = mutableListOf<ScanResult>()
        val candidates = (lastUsedByPkg.keys + launchCountByPkg.keys).toSet()

        for (pkg in candidates) {
            val lastUsed = lastUsedByPkg[pkg] ?: 0L
            val launches = launchCountByPkg[pkg] ?: 0
            val timeFg = totalTimeByPkg[pkg] ?: 0L
            if (lastUsed <= 0 && launches <= 0) continue

            // Cheat client Bedrock — CRITICAL si fue abierto.
            HackTerms.BEDROCK_CHEAT_PACKAGES[pkg]?.let { label ->
                out += build(
                    pkg = pkg, label = label,
                    tipo = "CHEAT_APP_LAUNCHED",
                    desc = "Cheat client lanzado: $label (${humanLastUsed(lastUsed)})",
                    alerta = "CRITICAL",
                    confidence = 0.96,
                    detected = listOf(
                        "blacklist:$pkg",
                        "launches:$launches",
                        "fg_minutes:${timeFg / 60_000}",
                    )
                )
                return@let
            }

            // Memory editor abierto — CRITICAL.
            HackTerms.MEMORY_EDITOR_PACKAGES[pkg]?.let { label ->
                out += build(
                    pkg = pkg, label = label,
                    tipo = "MEMORY_EDITOR_LAUNCHED",
                    desc = "Memory editor activo: $label (${humanLastUsed(lastUsed)})",
                    alerta = "CRITICAL",
                    confidence = 0.90,
                    detected = listOf(
                        "memhack:$pkg",
                        "launches:$launches",
                    )
                )
                return@let
            }

            // Root manager activo — SOSPECHOSO con confidence media (puede ser dev).
            HackTerms.ROOT_MANAGER_PACKAGES[pkg]?.let { label ->
                if (launches > 0) {
                    out += build(
                        pkg = pkg, label = label,
                        tipo = "ROOT_TOOL_ACTIVE",
                        desc = "Root manager fue abierto: $label",
                        alerta = "SOSPECHOSO",
                        confidence = 0.55,
                        detected = listOf("rootmgr:$pkg", "launches:$launches"),
                    )
                }
                return@let
            }

            // Heurística por nombre/term contra HACK_TERMS — SOSPECHOSO.
            val matched = HackTerms.HACK_TERMS.firstOrNull {
                smartHackMatch(pkg, it)
            }
            if (matched != null && pkg !in HackTerms.BEDROCK_CHEAT_PACKAGES &&
                pkg !in HackTerms.MEMORY_EDITOR_PACKAGES) {
                out += build(
                    pkg = pkg, label = pkg,
                    tipo = "CHEAT_APP_LAUNCHED_HEURISTIC",
                    desc = "Package lanzado con nombre que contiene '$matched'",
                    alerta = "SOSPECHOSO",
                    confidence = 0.62,
                    detected = listOf("term:$matched", "pkg:$pkg", "launches:$launches"),
                )
            }

            // Contexto Minecraft → INFO (no flag, ayuda al staff).
            HackTerms.MC_LAUNCHER_PACKAGES[pkg]?.let { info ->
                out += ScanResult(
                    tipo = "MC_LAUNCH_HISTORY",
                    categoria = "INFO",
                    nombre = info.displayName,
                    ruta = pkg,
                    descripcion = "Última sesión de ${info.displayName}: " +
                            "${humanLastUsed(lastUsed)} · $launches launch(es) en 30d",
                    confidence = 1.0,
                    alerta = "INFO",
                    detected_patterns = listOf(
                        "launcher:$pkg",
                        "launches:$launches",
                        "fg_min:${timeFg / 60_000}",
                    ),
                )
            }
        }
        return out
    }

    private fun build(
        pkg: String, label: String,
        tipo: String, desc: String, alerta: String,
        confidence: Double, detected: List<String>,
    ): ScanResult = ScanResult(
        tipo = tipo,
        categoria = if (alerta == "CRITICAL") "CRITICAL" else "SOSPECHOSO",
        nombre = label,
        ruta = pkg,
        descripcion = desc,
        confidence = confidence,
        alerta = alerta,
        detected_patterns = detected,
    )

    private fun humanLastUsed(ms: Long): String {
        if (ms <= 0) return "nunca"
        val delta = System.currentTimeMillis() - ms
        return when {
            delta < TimeUnit.MINUTES.toMillis(2)   -> "hace instantes"
            delta < TimeUnit.HOURS.toMillis(1)     -> "hace ${TimeUnit.MILLISECONDS.toMinutes(delta)} min"
            delta < TimeUnit.DAYS.toMillis(1)      -> "hace ${TimeUnit.MILLISECONDS.toHours(delta)} h"
            delta < TimeUnit.DAYS.toMillis(7)      -> "hace ${TimeUnit.MILLISECONDS.toDays(delta)} d"
            else -> SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date(ms))
        }
    }
}
