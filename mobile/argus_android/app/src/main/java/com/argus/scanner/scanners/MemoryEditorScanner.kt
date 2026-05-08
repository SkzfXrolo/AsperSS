package com.argus.scanner.scanners

import android.content.Context
import android.os.Environment
import com.argus.scanner.core.ScanCounters
import com.argus.scanner.core.ScanResult
import java.io.File

/**
 * MemoryEditorScanner — item #11 (Game Guardian + forks).
 *
 * Game Guardian no siempre se instala como APK formal — a veces el .elf
 * se dropea en /data/local/tmp y se ejecuta vía script. Esta clase busca
 * esos artefactos además de la detección por package_name (que la cubre
 * PackageScanner contra HackTerms.MEMORY_EDITOR_PACKAGES).
 */
class MemoryEditorScanner(
    private val ctx: Context,
    private val counters: ScanCounters? = null,
) {

    private val GG_TMP_PATHS = listOf(
        "/data/local/tmp/gg.elf",
        "/data/local/tmp/gg",
        "/data/local/tmp/gameguardian.elf",
        "/data/local/tmp/MGG",
    )

    private val GG_PUBLIC_PATHS = listOf(
        "Notes/GameGuardian",
        "GameGuardian",
        "Documents/GameGuardian",
    )

    fun scan(): List<ScanResult> {
        val results = mutableListOf<ScanResult>()
        val ext = Environment.getExternalStorageDirectory()

        for (p in GG_TMP_PATHS) {
            try {
                counters?.incFile()
                if (File(p).exists()) {
                    results += ScanResult(
                        tipo = "MEMORY_EDITOR_BINARY",
                        categoria = "CRITICAL",
                        nombre = File(p).name,
                        ruta = p,
                        descripcion = "Binario de Game Guardian dropeado en /data/local/tmp",
                        confidence = 0.85,
                        alerta = "CRITICAL",
                        detected_patterns = listOf("path:$p"),
                    )
                }
            } catch (_: Exception) { /* SELinux can block */ }
        }

        for (rel in GG_PUBLIC_PATHS) {
            val dir = File(ext, rel)
            if (!dir.exists() || !dir.canRead()) continue
            counters?.incDir()
            val children = dir.listFiles() ?: continue
            counters?.addFiles(children.size.toLong())
            // Cualquier carpeta GG con scripts adentro = evidencia clara.
            val scripts = children.filter {
                it.isFile && (it.name.endsWith(".lua", true) ||
                              it.name.endsWith(".gg",  true) ||
                              it.name.endsWith(".gpb", true))
            }
            if (scripts.isNotEmpty()) {
                results += ScanResult(
                    tipo = "MEMORY_EDITOR_SCRIPTS",
                    categoria = "CRITICAL",
                    nombre = dir.name,
                    ruta = dir.absolutePath,
                    descripcion = "Carpeta de scripts de Game Guardian con ${scripts.size} archivo(s)",
                    confidence = 0.88,
                    alerta = "CRITICAL",
                    detected_patterns = scripts.take(5).map { "script:${it.name}" },
                )
            }
        }

        return results
    }
}
