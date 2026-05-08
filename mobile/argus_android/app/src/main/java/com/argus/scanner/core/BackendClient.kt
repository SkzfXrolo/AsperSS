package com.argus.scanner.core

import android.os.Build
import com.argus.scanner.BuildConfig
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

/**
 * BackendClient — adaptador HTTP del scanner Android al backend Argus.
 *
 * Mismo contrato que el scanner desktop (Windows/Linux):
 *   1) POST /api/scans                  → crea el scan, devuelve scan_id
 *   2) POST /api/scans/<id>/results     → sube los hallazgos
 *
 * NO usamos OkHttp ni Gson para mantener APK <8MB (item #12). Solo
 * HttpURLConnection + org.json (built-in en Android).
 */
class BackendClient(
    private val token: String,
    private val baseUrl: String = BuildConfig.ARGUS_API_BASE,
) {

    /** POST /api/scans. Devuelve scan_id si OK, lanza IllegalStateException si no. */
    fun startScan(machineInfo: MachineInfo): Long {
        val body = JSONObject().apply {
            put("token",              token)
            put("machine_id",         machineInfo.machineId)
            put("machine_name",       machineInfo.deviceName)
            put("os",                 "Android")
            put("os_name",            machineInfo.osLabel)
            put("scanner_platform",   "android")
            put("scanner_version",    "1.6.49-android1")
            put("ip_address",         "")             // server-side fill
            put("country",            "")
            put("minecraft_username", machineInfo.minecraftHint)
            put("client_started_at",  System.currentTimeMillis() / 1000)
        }
        val resp = post("$baseUrl/api/scans", body.toString())
        val json = JSONObject(resp)
        if (json.has("error"))
            throw IllegalStateException(json.optString("error"))
        return json.optLong("scan_id", -1L).also {
            if (it <= 0) throw IllegalStateException("Backend no devolvió scan_id válido")
        }
    }

    /** POST /api/scans/<id>/results. screenshotB64 opcional (item #9). */
    fun submitResults(
        scanId: Long,
        results: List<ScanResult>,
        riskScore: Int,
        screenshotB64: String? = null,
        totalFilesScanned: Long = 0L,
        totalDirsScanned:  Long = 0L,
        scanDurationMs:    Long = 0L,
    ) {
        val arr = JSONArray()
        for (r in results) {
            arr.put(JSONObject().apply {
                put("tipo",                r.tipo)
                put("categoria",           r.categoria)
                put("nombre",              r.nombre)
                put("ruta",                r.ruta)
                put("descripcion",         r.descripcion)
                put("confidence",          r.confidence)
                put("alerta",              r.alerta)
                put("detected_patterns",   JSONArray(r.detected_patterns))
                if (r.file_hash != null) put("file_hash", r.file_hash)
            })
        }
        val body = JSONObject().apply {
            put("token",       token)
            put("scan_id",     scanId)
            put("results",     arr)
            put("risk_score",  riskScore)
            put("status",      "completed")
            put("client_finished_at", System.currentTimeMillis() / 1000)
            // Mismo contrato que scanner desktop (Windows/Linux). Si se
            // omite, el panel staff muestra "0 archivos escaneados".
            put("total_files_scanned", totalFilesScanned)
            put("total_dirs_scanned",  totalDirsScanned)
            put("issues_found",        results.size)
            if (scanDurationMs > 0) put("scan_duration", scanDurationMs / 1000.0)
            if (!screenshotB64.isNullOrBlank()) put("screenshot", screenshotB64)
        }
        val resp = post("$baseUrl/api/scans/$scanId/results", body.toString())
        val json = JSONObject(resp)
        if (json.has("error"))
            throw IllegalStateException(json.optString("error"))
    }

    private fun post(url: String, body: String): String {
        val u = URL(url)
        val conn = (u.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            connectTimeout = 15_000
            readTimeout = 30_000
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("User-Agent",
                "Argus-Android/${BuildConfig.VERSION_NAME} (Android ${Build.VERSION.RELEASE})")
        }
        try {
            conn.outputStream.use { it.write(body.toByteArray(StandardCharsets.UTF_8)) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val resp = stream?.bufferedReader(StandardCharsets.UTF_8)?.use { it.readText() }
                ?: ""
            if (code !in 200..299)
                throw IllegalStateException("HTTP $code: ${resp.take(300)}")
            return resp
        } finally {
            conn.disconnect()
        }
    }
}

data class MachineInfo(
    val machineId: String,
    val deviceName: String,
    val osLabel: String,
    val minecraftHint: String,
)
