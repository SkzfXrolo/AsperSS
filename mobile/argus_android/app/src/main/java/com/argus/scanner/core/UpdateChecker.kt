package com.argus.scanner.core

import android.os.Build
import com.argus.scanner.BuildConfig
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

/**
 * UpdateChecker — Item Android #15.
 *
 * Consulta `${ARGUS_API_BASE}/api/android-version?current=<commit>` al
 * iniciar la app. Si el backend reporta un APK más reciente publicado
 * en GitHub Releases, devuelve un [UpdateInfo] con la URL del APK; la
 * UI muestra un banner con botón "Actualizar" que abre un Intent.VIEW
 * sobre esa URL para que el navegador descargue el APK firmado y el
 * usuario complete la instalación con el dialog del SO.
 *
 * Notas de diseño:
 *   * Network-only (sin DB): el chequeo es barato (~1 KB JSON) y no
 *     queremos persistir versiones obsoletas.
 *   * Falla silenciosa: si el backend está caído o no hay red, devuelve
 *     null. La app sigue funcionando con la versión actual.
 *   * No instala la APK por nosotros (haría falta REQUEST_INSTALL_PACKAGES
 *     + un FileProvider + descarga local). Delegamos al navegador, que
 *     ya tiene UX nativa para "abrir APK descargado" en todos los OEM.
 */
class UpdateChecker(
    private val baseUrl: String = BuildConfig.ARGUS_API_BASE,
) {

    /** Versión local: el commit corto que el workflow CI inyectó al buildear. */
    val currentCommit: String get() = BuildConfig.ARGUS_BUILD_COMMIT

    /**
     * Bloquea ~5s. Llamar desde Dispatchers.IO. Devuelve null si no hay
     * red, el backend falla, o no hay actualización disponible.
     *
     * Body en bloque (no expression body) porque adentro hay `return null`
     * early-exits — Kotlin no permite returns en funciones con expression
     * body (`= try { ... }`).
     */
    fun check(): UpdateInfo? {
        return try {
            val url = URL("$baseUrl/api/android-version?current=$currentCommit")
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod  = "GET"
                connectTimeout = 4_000
                readTimeout    = 5_000
                setRequestProperty("User-Agent",
                    "Argus-Android/${BuildConfig.VERSION_NAME} (Android ${Build.VERSION.RELEASE})")
            }
            try {
                val code = conn.responseCode
                if (code !in 200..299) return null
                val raw = conn.inputStream.bufferedReader(StandardCharsets.UTF_8)
                    .use { it.readText() }
                val json = JSONObject(raw)
                val updateAvailable = json.optBoolean("update_available", false)
                val apkUrl = json.optString("apk_url", "")
                    .takeIf { it.isNotBlank() } ?: return null
                val shortCommit = json.optString("short_commit", "")
                    .takeIf { it.isNotBlank() }
                val publishedAt = json.optString("published_at", "")
                    .takeIf { it.isNotBlank() }
                val releaseNotes = json.optString("release_notes", "")
                    .takeIf { it.isNotBlank() }
                // Si current es "dev" (build local) no notificamos: el dev
                // sabe qué tiene. Solo notifica cuando la app es build firmada.
                if (currentCommit == "dev") return null
                if (!updateAvailable) return null
                UpdateInfo(
                    latestCommit  = shortCommit,
                    apkUrl        = apkUrl,
                    publishedAt   = publishedAt,
                    releaseNotes  = releaseNotes,
                    currentCommit = currentCommit,
                )
            } finally {
                conn.disconnect()
            }
        } catch (_: Exception) {
            null
        }
    }
}

data class UpdateInfo(
    val latestCommit: String?,
    val apkUrl: String,
    val publishedAt: String?,
    val releaseNotes: String?,
    val currentCommit: String,
)
