package com.argus.scanner.scanners

import android.content.Context
import android.os.Build
import android.os.Environment
import android.os.FileObserver
import com.argus.scanner.core.HackTerms
import com.argus.scanner.core.LegitMods
import com.argus.scanner.core.ScanResult
import com.argus.scanner.core.smartHackMatch
import kotlinx.coroutines.delay
import java.io.File
import java.util.concurrent.ConcurrentLinkedQueue

/**
 * FileObserverScanner — item Android #5.
 *
 * Equivalente Android de la USN Journal de NTFS. Android NO guarda log
 * persistente de operaciones de archivos, así que la única opción es
 * observar EN VIVO durante una ventana corta del scan (~12s default).
 *
 * Atacha FileObserver a los paths críticos de Minecraft + Download:
 *   /sdcard/games/com.mojang/                              (Bedrock root)
 *   /sdcard/Android/data/com.mojang.minecraftpe/files/games/com.mojang/
 *   /sdcard/Android/data/net.kdt.pojavlaunch/files/.minecraft/
 *   /sdcard/Android/data/net.kdt.pojavlauncher/files/.minecraft/
 *   /sdcard/Android/data/com.boardwalk.boardwalk/files/.minecraft/
 *   /sdcard/Android/data/com.mcpemaster.mcpe/files/
 *   /sdcard/Download/                                      (APKs sideload)
 *   /sdcard/AppPacks/                                      (Toolbox addons)
 *   /sdcard/Movies/Minecraft/                              (recordings)
 *
 * Eventos capturados: CREATE, MODIFY, DELETE, MOVED_TO. Cada uno con
 * smart_hack_match contra HACK_TERMS y excluyendo LegitMods. Si en la
 * ventana del scan se crea/modifica un archivo con hack-term match
 * → CRITICAL "actividad sospechosa durante el scan".
 *
 * Importante:
 *  - FileObserver con API < 29 acepta SOLO el path como String.
 *  - API ≥ 29 también soporta File. Usamos String por compatibilidad.
 *  - El observer no es recursivo por defecto. Si el path tiene
 *    subcarpetas (mods/, addons/, behavior_packs/) montamos un observer
 *    por cada hijo importante hasta depth=2.
 */
class FileObserverScanner(private val ctx: Context) {

    private val findings = ConcurrentLinkedQueue<ScanResult>()
    private val observers = mutableListOf<FileObserver>()

    /** Lanza los watchers durante [windowMs] ms y devuelve los hits. */
    suspend fun observe(windowMs: Long = 12_000L): List<ScanResult> {
        val sd = Environment.getExternalStorageDirectory()
        val targets = listOf(
            File(sd, "games/com.mojang"),
            File(sd, "Android/data/com.mojang.minecraftpe/files/games/com.mojang"),
            File(sd, "Android/data/net.kdt.pojavlaunch/files/.minecraft"),
            File(sd, "Android/data/net.kdt.pojavlauncher/files/.minecraft"),
            File(sd, "Android/data/com.boardwalk.boardwalk/files/.minecraft"),
            File(sd, "Android/data/com.mcpemaster.mcpe/files"),
            File(sd, "Download"),
            File(sd, "AppPacks"),
            File(sd, "Movies/Minecraft"),
        ).filter { it.exists() && it.canRead() }

        if (targets.isEmpty()) return emptyList()

        val expanded = mutableListOf<File>()
        for (root in targets) {
            expanded += root
            // Subcarpetas comunes de mods/addons (no recursivo full por costo).
            for (sub in listOf("mods", "addons", "behavior_packs", "resource_packs",
                                "scripts", "versions", "config")) {
                val s = File(root, sub)
                if (s.exists() && s.isDirectory && s.canRead()) expanded += s
            }
        }

        for (dir in expanded) {
            try {
                val obs = build(dir)
                obs.startWatching()
                observers += obs
            } catch (_: Throwable) { /* algunas paths fallan por SE Linux */ }
        }

        delay(windowMs)

        for (obs in observers) {
            try { obs.stopWatching() } catch (_: Throwable) {}
        }
        observers.clear()
        return findings.toList()
    }

    private fun build(dir: File): FileObserver {
        val mask = FileObserver.CREATE or FileObserver.MODIFY or
                   FileObserver.DELETE or FileObserver.MOVED_TO or
                   FileObserver.MOVED_FROM
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            object : FileObserver(dir, mask) {
                override fun onEvent(event: Int, path: String?) {
                    handleEvent(dir, event, path)
                }
            }
        } else {
            @Suppress("DEPRECATION")
            object : FileObserver(dir.absolutePath, mask) {
                override fun onEvent(event: Int, path: String?) {
                    handleEvent(dir, event, path)
                }
            }
        }
    }

    private fun handleEvent(dir: File, event: Int, path: String?) {
        if (path.isNullOrBlank()) return
        val full = File(dir, path).absolutePath
        val lower = path.lowercase()

        // Filtrar archivos que no nos interesan (txt, dbtmp, .lock, etc).
        val ext = lower.substringAfterLast('.', "")
        if (ext !in EXT_OF_INTEREST && !lower.endsWith(".jar") &&
            !lower.endsWith(".dex") && !lower.endsWith(".apk")) return

        // Excluir si matchea legit mod (sodium, fabric-api, jei, geyser…).
        if (LegitMods.isLegitJavaMod(lower) || LegitMods.isLegitBedrockAddon(lower)) return

        val matched = HackTerms.HACK_TERMS.firstOrNull { smartHackMatch(lower, it) }
            ?: return

        val verb = when {
            event and FileObserver.CREATE != 0 -> "CREATED"
            event and FileObserver.MODIFY != 0 -> "MODIFIED"
            event and FileObserver.DELETE != 0 -> "DELETED"
            event and FileObserver.MOVED_TO != 0 -> "MOVED"
            event and FileObserver.MOVED_FROM != 0 -> "MOVED_OUT"
            else -> "TOUCHED"
        }

        findings += ScanResult(
            tipo = "LIVE_FILE_ACTIVITY",
            categoria = "CRITICAL",
            nombre = path,
            ruta = full,
            descripcion = "$verb durante el scan: $path · matchea '$matched'",
            confidence = 0.86,
            alerta = "CRITICAL",
            detected_patterns = listOf(
                "live:$verb",
                "term:$matched",
                "ext:.${ext}",
            ),
        )
    }

    companion object {
        private val EXT_OF_INTEREST = setOf(
            "jar", "zip", "dex", "apk", "mcpack", "mcaddon",
            "mcworld", "mctemplate", "js", "lua", "gg", "gpb",
            "elf", "so", "bin",
        )
    }
}
