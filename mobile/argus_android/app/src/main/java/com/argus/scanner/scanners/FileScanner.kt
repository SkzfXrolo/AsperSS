package com.argus.scanner.scanners

import android.content.Context
import android.os.Environment
import com.argus.scanner.core.HackTerms
import com.argus.scanner.core.ScanCounters
import com.argus.scanner.core.ScanResult
import com.argus.scanner.core.smartHackMatch
import java.io.File

/**
 * FileScanner — items #3 (papelera/borrados aprox), #5 (file activity).
 *
 * NOTA HONESTA: Android no expone una "papelera global". Esta versión
 * busca:
 *  - /sdcard/Download/                        (APKs sideloaded)
 *  - /sdcard/.recycle, .recyclebin, RecycleBin
 *  - /sdcard/.MIRecycleBin                    (Mi File Manager)
 *  - /sdcard/.SE_Recycle                      (Solid Explorer)
 *  - /sdcard/Android/data/com.android.providers.media.module/cache/
 *  - /sdcard/DCIM/.thumbnails                 (huellas de archivos borrados)
 *
 * El cubrimiento de MediaStore IS_TRASHED via ContentResolver se deja
 * para Pack 26 (requiere persistir lifetime más largo del cursor).
 */
class FileScanner(
    private val ctx: Context,
    private val counters: ScanCounters? = null,
) {

    private val EXTERNAL = Environment.getExternalStorageDirectory()

    fun scan(): List<ScanResult> {
        val results = mutableListOf<ScanResult>()

        // Carpetas tipo "papelera" (item #3)
        val recycleRoots = listOf(
            ".recycle", ".recyclebin", "RecycleBin",
            ".MIRecycleBin",   // Mi File Manager (Xiaomi)
            ".SE_Recycle",     // Solid Explorer
            "CXFileExplorer/Recycle",
            "Trash",
        ).map { File(EXTERNAL, it) }
        for (r in recycleRoots) scanFolder(r, "RECYCLE", results)

        // Download/ — sideload de APKs y .jar/.zip de hacks
        scanFolder(File(EXTERNAL, "Download"), "DOWNLOAD", results)

        // Movies/Minecraft — recordings que pueden tener hacks visibles
        // (informativo, no flag)
        // Movies/* generalmente legítimo, lo dejamos fuera.

        // /sdcard/AppPacks — Toolbox addons location
        scanFolder(File(EXTERNAL, "AppPacks"), "TOOLBOX_ADDONS", results)

        // games/com.mojang/ — el path público de Bedrock; muchos cheats
        // cargan addons aquí.
        scanFolder(File(EXTERNAL, "games/com.mojang"), "BEDROCK_PUBLIC", results)

        return results
    }

    private fun scanFolder(root: File, label: String, out: MutableList<ScanResult>) {
        if (!root.exists() || !root.canRead()) return
        val toCheck = mutableListOf<File>()
        try {
            walk(root, depth = 4, toCheck)
        } catch (_: Exception) { return }

        for (f in toCheck) {
            val name = f.name
            val lower = name.lowercase()
            val isInteresting = lower.endsWith(".apk") || lower.endsWith(".jar") ||
                                lower.endsWith(".zip") || lower.endsWith(".dex") ||
                                lower.endsWith(".mcpack") || lower.endsWith(".mcaddon") ||
                                lower.endsWith(".mcworld") || lower.endsWith(".js")
            if (!isInteresting) continue

            for (term in HackTerms.HACK_TERMS) {
                if (smartHackMatch(name, term)) {
                    val tipo = when (label) {
                        "RECYCLE"           -> "FILE_RECYCLED_HACK"
                        "DOWNLOAD"          -> "DOWNLOADED_HACK"
                        "TOOLBOX_ADDONS"    -> "TOOLBOX_ADDON_HACK"
                        "BEDROCK_PUBLIC"    -> "BEDROCK_PUBLIC_HACK"
                        else                -> "FILE_HACK"
                    }
                    out += ScanResult(
                        tipo = tipo,
                        categoria = "CRITICAL",
                        nombre = name,
                        ruta = f.absolutePath,
                        descripcion = "Archivo en $label con token '$term'",
                        confidence = if (label == "RECYCLE") 0.78 else 0.85,
                        alerta = "CRITICAL",
                        detected_patterns = listOf("term:$term", "loc:$label"),
                    )
                    break
                }
            }
        }
    }

    private fun walk(root: File, depth: Int, out: MutableList<File>) {
        if (depth < 0) return
        val ch = root.listFiles() ?: return
        counters?.incDir()
        for (c in ch) {
            try {
                if (c.isDirectory) {
                    walk(c, depth - 1, out)
                } else {
                    out += c
                    counters?.incFile()
                }
            } catch (_: Exception) { /* SAF restrictions */ }
        }
    }
}
