package com.argus.scanner.scanners

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.os.Build
import android.os.Process
import com.argus.scanner.core.HackTerms
import com.argus.scanner.core.ScanResult
import com.argus.scanner.core.smartHackMatch
import java.util.concurrent.TimeUnit

/**
 * OverlayScanner — item Android #7.
 *
 * Vector clásico de cheating móvil: una app SECUNDARIA dibuja por encima
 * de Minecraft (ESP/Wallhack/Aim arrows). El cheat NO modifica el .apk
 * de Minecraft → el package match desktop no lo pesca. Lo único que
 * delata es que tiene OP_SYSTEM_ALERT_WINDOW concedido y estuvo activo
 * mientras minecraftpe corría en foreground.
 *
 * Doble check:
 *   1) AppOpsManager.checkOpNoThrow(OP_SYSTEM_ALERT_WINDOW, uid, pkg)
 *      por TODOS los packages instalados → lista de apps con permiso
 *      "Display over other apps".
 *   2) UsageStatsManager.queryEvents → últimos 5 minutos: ¿hubo una
 *      app overlay en foreground mientras minecraftpe / pojavlaunch
 *      también estaba activo?
 *
 * Reporta:
 *  - CRITICAL si overlay activo + minecraftpe foreground en última hora
 *    + label/pkg matchea HACK_TERMS.
 *  - SOSPECHOSO si overlay activo + label/pkg matchea HACK_TERMS pero
 *    sin context Minecraft (puede ser cheat de OTRO juego).
 *  - INFO si overlay genérico (apps legítimas como Twitch, Facebook
 *    Messenger, Lockwatch — no flag, solo contexto).
 *
 * Permiso requerido: PACKAGE_USAGE_STATS (mismo que UsageStatsScanner).
 * Sin él, el cross-check con foreground no funciona — degrada a
 * "lista de apps con overlay" sin prioridad.
 */
class OverlayScanner(private val ctx: Context) {

    fun scan(): List<ScanResult> {
        val pm = ctx.packageManager
        val ops = ctx.getSystemService(Context.APP_OPS_SERVICE) as? AppOpsManager
            ?: return emptyList()

        // 1) Lista todas las apps con OP_SYSTEM_ALERT_WINDOW concedido.
        val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
            PackageManager.PackageInfoFlags.of(0L)
        else null
        val pkgs = try {
            if (flags != null)
                pm.getInstalledPackages(flags)
            else
                @Suppress("DEPRECATION") pm.getInstalledPackages(0)
        } catch (_: Exception) { return emptyList() }

        val overlayed = mutableListOf<OverlayHit>()
        for (info in pkgs) {
            val app = info.applicationInfo ?: continue
            val pkg = info.packageName ?: continue
            // Saltear el propio Argus.
            if (pkg == ctx.packageName) continue
            // Saltear apps del sistema sin UI (Settings, FaceUnlock…).
            if ((app.flags and ApplicationInfo.FLAG_SYSTEM) != 0 &&
                (app.flags and ApplicationInfo.FLAG_UPDATED_SYSTEM_APP) == 0) continue

            val mode = try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    ops.unsafeCheckOpNoThrow(
                        AppOpsManager.OPSTR_SYSTEM_ALERT_WINDOW,
                        app.uid, pkg
                    )
                } else {
                    @Suppress("DEPRECATION")
                    ops.checkOpNoThrow(
                        AppOpsManager.OPSTR_SYSTEM_ALERT_WINDOW,
                        app.uid, pkg
                    )
                }
            } catch (_: Exception) { AppOpsManager.MODE_DEFAULT }

            if (mode == AppOpsManager.MODE_ALLOWED) {
                val label = try { pm.getApplicationLabel(app).toString() } catch (_: Exception) { pkg }
                overlayed += OverlayHit(pkg, label)
            }
        }

        if (overlayed.isEmpty()) return emptyList()

        // 2) ¿Estuvo Minecraft en foreground en la última hora?
        val mcRecent = recentMinecraftSession()

        val out = mutableListOf<ScanResult>()
        for (ov in overlayed) {
            // Skip apps que sabemos legítimas (Discord/messenger/Twitch chat
            // overlay/Facebook chathead/Twitter/Bubbles del SO).
            if (ov.pkg in BENIGN_OVERLAY_PKGS) continue

            // Cheat client conocido con overlay → CRITICAL automático.
            HackTerms.BEDROCK_CHEAT_PACKAGES[ov.pkg]?.let { hit ->
                out += ScanResult(
                    tipo = "OVERLAY_CHEAT_ACTIVE",
                    categoria = "CRITICAL",
                    nombre = hit,
                    ruta = ov.pkg,
                    descripcion = "Cheat client con permiso de overlay activo: $hit" +
                            (if (mcRecent) " · Minecraft foreground en última hora" else ""),
                    confidence = if (mcRecent) 0.97 else 0.85,
                    alerta = "CRITICAL",
                    detected_patterns = listOf(
                        "overlay:on",
                        "blacklist:${ov.pkg}",
                        if (mcRecent) "mc_recent:true" else "mc_recent:false",
                    ),
                )
                return@let
            }

            // Memory editor con overlay (Game Guardian flotante).
            HackTerms.MEMORY_EDITOR_PACKAGES[ov.pkg]?.let { hit ->
                out += ScanResult(
                    tipo = "OVERLAY_MEMORY_EDITOR",
                    categoria = if (mcRecent) "CRITICAL" else "SOSPECHOSO",
                    nombre = hit,
                    ruta = ov.pkg,
                    descripcion = "Memory editor con overlay activo: $hit" +
                            (if (mcRecent) " · ESP/aim sobre Minecraft" else ""),
                    confidence = if (mcRecent) 0.95 else 0.70,
                    alerta = if (mcRecent) "CRITICAL" else "SOSPECHOSO",
                    detected_patterns = listOf(
                        "overlay:on",
                        "memhack:${ov.pkg}",
                        if (mcRecent) "mc_recent:true" else "mc_recent:false",
                    ),
                )
                return@let
            }

            // Heurística: app desconocida con label/pkg matchea HACK_TERMS.
            val term = HackTerms.HACK_TERMS.firstOrNull {
                smartHackMatch(ov.label, it) || smartHackMatch(ov.pkg, it)
            }
            if (term != null) {
                out += ScanResult(
                    tipo = "OVERLAY_HEURISTIC",
                    categoria = if (mcRecent) "CRITICAL" else "SOSPECHOSO",
                    nombre = ov.label,
                    ruta = ov.pkg,
                    descripcion = "Overlay activo con nombre que contiene '$term'" +
                            (if (mcRecent) " durante sesión de Minecraft" else ""),
                    confidence = if (mcRecent) 0.80 else 0.55,
                    alerta = if (mcRecent) "CRITICAL" else "SOSPECHOSO",
                    detected_patterns = listOf(
                        "overlay:on",
                        "term:$term",
                        if (mcRecent) "mc_recent:true" else "mc_recent:false",
                    ),
                )
            }
        }
        return out
    }

    /** ¿Hubo ACTIVITY_RESUMED de un launcher MC en los últimos 60 min? */
    private fun recentMinecraftSession(): Boolean {
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
        if (mode != AppOpsManager.MODE_ALLOWED) return false

        val usm = ctx.getSystemService(Context.USAGE_STATS_SERVICE) as? UsageStatsManager
            ?: return false
        val now = System.currentTimeMillis()
        val begin = now - TimeUnit.HOURS.toMillis(1)
        return try {
            val ev = UsageEvents.Event()
            val events = usm.queryEvents(begin, now)
            while (events.hasNextEvent()) {
                events.getNextEvent(ev)
                if (ev.eventType == UsageEvents.Event.ACTIVITY_RESUMED ||
                    ev.eventType == UsageEvents.Event.MOVE_TO_FOREGROUND) {
                    if (ev.packageName in HackTerms.MC_LAUNCHER_PACKAGES.keys) return true
                }
            }
            false
        } catch (_: Exception) { false }
    }

    private data class OverlayHit(val pkg: String, val label: String)

    companion object {
        // Apps legítimas conocidas que usan overlays (no flagear).
        private val BENIGN_OVERLAY_PKGS = setOf(
            "com.facebook.orca",          // Messenger chat heads
            "com.facebook.katana",        // Facebook
            "com.whatsapp",
            "com.discord",
            "com.tv.twitch.android.app",
            "tv.twitch.android.app",
            "com.twitter.android",
            "com.instagram.android",
            "com.spotify.music",
            "com.android.systemui",
            "com.google.android.apps.maps",
            "com.skype.raider",
            "com.zoom.us",
            "us.zoom.videomeetings",
        )
    }
}
