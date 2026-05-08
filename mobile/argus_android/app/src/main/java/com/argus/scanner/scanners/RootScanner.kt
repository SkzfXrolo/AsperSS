package com.argus.scanner.scanners

import android.os.Build
import com.argus.scanner.core.ScanResult
import java.io.File

/**
 * RootScanner — item #10 (root / Magisk / Xposed / KernelSU).
 *
 * Múltiples checks redundantes. Cada cheat-detection app esquiva uno u
 * otro vector — combinarlos eleva mucho la tasa de detección sin pedir
 * permisos adicionales.
 *
 * Nota: la presencia de root NO es CRITICAL automático — el usuario
 * puede ser developer o tener el celu rooteado para AdAway. Reportamos
 * SOSPECHOSO con confidence baja y dejamos el veredicto al staff.
 */
class RootScanner {

    private val ROOT_PATHS = listOf(
        "/system/xbin/su",
        "/sbin/su",
        "/system/bin/su",
        "/system/app/Superuser.apk",
        "/system/app/SuperSU.apk",
        "/system/app/Kinguser.apk",
        "/sbin/.magisk",
        "/data/adb/magisk",
        "/data/adb/lspd",                  // LSPosed daemon
        "/data/adb/ksu",                   // KernelSU
        "/data/local/tmp/magisk_aux",
        "/system/etc/init.d",
    )

    fun scan(): List<ScanResult> {
        val results = mutableListOf<ScanResult>()

        // 1) Existencia de paths de root
        val foundPaths = ROOT_PATHS.filter { p ->
            try { File(p).exists() } catch (_: Exception) { false }
        }
        if (foundPaths.isNotEmpty()) {
            results += ScanResult(
                tipo = "DEVICE_ROOTED",
                categoria = "SOSPECHOSO",
                nombre = "Root detectado",
                ruta = foundPaths.first(),
                descripcion = "Indicadores de root presentes: ${foundPaths.joinToString(", ").take(180)}",
                confidence = 0.55,
                alerta = "SOSPECHOSO",
                detected_patterns = foundPaths.map { "path:$it" },
            )
        }

        // 2) Build.TAGS contiene "test-keys" (custom kernel)
        val tags = Build.TAGS ?: ""
        if (tags.contains("test-keys")) {
            results += ScanResult(
                tipo = "CUSTOM_KERNEL",
                categoria = "SOSPECHOSO",
                nombre = "Build con test-keys",
                ruta = "Build.TAGS",
                descripcion = "Build.TAGS = '$tags' — kernel custom o ROM no oficial.",
                confidence = 0.40,
                alerta = "SOSPECHOSO",
                detected_patterns = listOf("tags:test-keys"),
            )
        }

        // 3) Intentar exec("which su") — works si rooted Y SELinux permisivo.
        try {
            val proc = ProcessBuilder("/system/bin/which", "su")
                .redirectErrorStream(true).start()
            val out = proc.inputStream.bufferedReader().readText()
            proc.waitFor()
            if (out.contains("/su")) {
                results += ScanResult(
                    tipo = "DEVICE_ROOTED",
                    categoria = "SOSPECHOSO",
                    nombre = "su accesible vía PATH",
                    ruta = out.trim(),
                    descripcion = "El comando 'which su' devolvió un path → root activo.",
                    confidence = 0.60,
                    alerta = "SOSPECHOSO",
                    detected_patterns = listOf("which:${out.trim()}"),
                )
            }
        } catch (_: Exception) { /* SELinux blocks → no info */ }

        return results
    }
}
