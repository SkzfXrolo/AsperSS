package com.argus.scanner.core

import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import com.argus.scanner.scanners.FileObserverScanner
import com.argus.scanner.scanners.FileScanner
import com.argus.scanner.scanners.LauncherScanner
import com.argus.scanner.scanners.MemoryEditorScanner
import com.argus.scanner.scanners.OverlayScanner
import com.argus.scanner.scanners.PackageScanner
import com.argus.scanner.scanners.RootScanner
import com.argus.scanner.scanners.ScreenshotCapture
import com.argus.scanner.scanners.UsageStatsScanner
import com.argus.scanner.service.ScanForegroundService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.FlowCollector
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn

/**
 * ScanOrchestrator — corre todos los scanners móviles en orden, agrega
 * los resultados, aplica el filtro Bayesian-lite móvil, calcula risk
 * score y los sube al backend Argus.
 *
 * Orden Pack 26:
 *   FileObserverScanner se lanza en paralelo (12s window) al inicio.
 *   1) PackageScanner          — items #6, #11
 *   2) UsageStatsScanner       — item #4 (Prefetch móvil)
 *   3) RootScanner             — item #10
 *   4) MemoryEditorScanner     — item #11
 *   5) OverlayScanner          — item #7 (overlays + cross-check MC)
 *   6) LauncherScanner         — item #8
 *   7) FileScanner             — items #3, #5 estático
 *   8) Esperar FileObserver    — item #5 runtime
 *
 * El screenshot (item #9) se captura tras los scanners si la activity
 * obtuvo el consent de MediaProjection.
 *
 * Risk scoring (mismo que desktop):
 *   CRITICAL → +25 cada uno (cap +60)
 *   SOSPECHOSO → +6 cada uno (cap +20)
 *   INFO → +0
 *
 * Verdict:
 *   ≥ 70 HACK_DETECTADO
 *   ≥ 30 SOSPECHOSO
 *   else LIMPIO
 *
 * El backend recalcula con su propio ensemble (RF + heuristic + AI),
 * así que este score local es solo display previo al round-trip.
 */
class ScanOrchestrator(private val ctx: Context) {

    fun run(
        token: String,
        screenshotResultCode: Int = 0,
        screenshotData: Intent? = null,
    ): Flow<ScanProgressEvent> = flow {
        emit(ScanProgressEvent.Log("→ Argus Android · v1.6.49 (Pack 26)"))
        // Validación mínima — el backend Argus rechaza tokens inválidos al
        // crear el scan. Tokens del staff son típicamente 6 chars, pero
        // dejamos margen para 4-12 por compatibilidad con futuros formatos.
        val cleanToken = token.trim()
        if (cleanToken.length < 4) {
            emit(ScanProgressEvent.Failed("Token inválido o demasiado corto"))
            return@flow
        }

        ScanForegroundService.start(ctx)
        try {
            val client = BackendClient(cleanToken)
            val machine = collectMachineInfo()
            emit(ScanProgressEvent.Log("→ Subiendo handshake al backend…"))
            val scanId = try { client.startScan(machine) }
            catch (e: Exception) {
                emit(ScanProgressEvent.Failed("No se pudo iniciar scan: ${e.message}"))
                return@flow
            }
            emit(ScanProgressEvent.ScanCreated(scanId))
            emit(ScanProgressEvent.Log("[OK] Scan #$scanId creado"))

            val all = mutableListOf<ScanResult>()
            coroutineScope {
                val observerJob = async(Dispatchers.IO) {
                    try { FileObserverScanner(ctx).observe(12_000L) }
                    catch (_: Throwable) { emptyList() }
                }

                runStep(this@flow, "Revisando apps instaladas (cheats / memhacks / root)") {
                    PackageScanner(ctx).scan()
                }.also { all += it }

                // UsageStats es opcional. Si la ROM lo bloquea (Honor MagicOS,
                // Huawei EMUI, "Ajustes restringidos" en HyperOS), reportamos
                // al log para que el staff sepa que el scan corrió en modo
                // parcial — pero NO abortamos el scan.
                val usageScanner = UsageStatsScanner(ctx)
                if (usageScanner.hasPermission()) {
                    runStep(this@flow, "Apps lanzadas recientemente (Prefetch móvil)") {
                        usageScanner.scan()
                    }.also { all += it }
                } else {
                    emit(ScanProgressEvent.Log(
                        "[!] UsageStats deshabilitado (ROM bloquea sideload) — " +
                        "saltando A#4. Detección por package/archivo sigue activa."
                    ))
                }

                runStep(this@flow, "Detectando root / Magisk / LSPosed / KernelSU") {
                    RootScanner().scan()
                }.also { all += it }

                runStep(this@flow, "Buscando memory editors (Game Guardian + scripts)") {
                    MemoryEditorScanner(ctx).scan()
                }.also { all += it }

                runStep(this@flow, "Cazando overlays activos (ESP / wallhack flotante)") {
                    OverlayScanner(ctx).scan()
                }.also { all += it }

                runStep(this@flow, "Inspeccionando launchers Minecraft móvil") {
                    LauncherScanner(ctx).scan()
                }.also { all += it }

                runStep(this@flow, "Revisando archivos sospechosos en /sdcard") {
                    FileScanner(ctx).scan()
                }.also { all += it }

                emit(ScanProgressEvent.Log("→ Cerrando watchers de archivos…"))
                val live = try { observerJob.await() } catch (_: Throwable) { emptyList() }
                emit(ScanProgressEvent.Log("[OK] ${live.size} actividad(es) en vivo"))
                all += live
            }

            // Filtro Bayesian-lite móvil
            val filtered = mutableListOf<ScanResult>()
            var dropped = 0
            for (r in all) {
                val keep = applyBayesianFilter(r)
                if (keep != null) filtered += keep else dropped++
            }
            if (dropped > 0)
                emit(ScanProgressEvent.Log("[OK] Bayesian-lite descartó $dropped FP"))

            val score = computeRiskScore(filtered)
            val verdict = when {
                score >= 70 -> "HACK_DETECTADO"
                score >= 30 -> "SOSPECHOSO"
                else        -> "LIMPIO"
            }
            emit(ScanProgressEvent.Log("→ Risk score local: $score · $verdict"))

            val screenshotB64: String? = if (screenshotData != null) {
                emit(ScanProgressEvent.Log("→ Capturando pantalla (MediaProjection)…"))
                try { ScreenshotCapture(ctx).captureToBase64(screenshotResultCode, screenshotData) }
                catch (e: Exception) {
                    emit(ScanProgressEvent.Log("[!] Screenshot falló: ${e.message}"))
                    null
                }
            } else null
            if (!screenshotB64.isNullOrBlank())
                emit(ScanProgressEvent.Log("[OK] Screenshot: ${screenshotB64.length} chars b64"))

            emit(ScanProgressEvent.Log("→ Enviando ${filtered.size} hallazgo(s) al panel…"))
            try {
                client.submitResults(scanId, filtered, score, screenshotB64)
                emit(ScanProgressEvent.Log("[OK] Resultados subidos correctamente"))
                emit(ScanProgressEvent.Done(score, verdict))
            } catch (e: Exception) {
                emit(ScanProgressEvent.Failed("Error subiendo resultados: ${e.message}"))
            }
        } finally {
            ScanForegroundService.stop(ctx)
        }
    }.flowOn(Dispatchers.IO)

    private suspend inline fun runStep(
        collector: FlowCollector<ScanProgressEvent>,
        message: String,
        block: () -> List<ScanResult>,
    ): List<ScanResult> {
        collector.emit(ScanProgressEvent.Log("→ $message"))
        return try {
            val r = block()
            collector.emit(ScanProgressEvent.Log("[OK] ${r.size} hallazgo(s)"))
            r
        } catch (e: Throwable) {
            collector.emit(ScanProgressEvent.Log("[!] falló: ${e.message}"))
            emptyList()
        }
    }

    private fun computeRiskScore(results: List<ScanResult>): Int {
        var score = 0
        var critCount = 0
        var susCount  = 0
        for (r in results) {
            when (r.alerta) {
                "CRITICAL" -> {
                    if (critCount < 3) score += 25
                    else if (critCount < 6) score += 5
                    critCount++
                }
                "SOSPECHOSO" -> {
                    if (susCount < 4) score += 6
                    susCount++
                }
            }
        }
        return score.coerceAtMost(100)
    }

    private fun collectMachineInfo(): MachineInfo {
        val androidId = try {
            Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ANDROID_ID) ?: "unknown"
        } catch (_: Exception) { "unknown" }
        val brand = "${Build.MANUFACTURER} ${Build.MODEL}".trim()
        val osLabel = "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})"
        return MachineInfo(
            machineId = "android:" + androidId,
            deviceName = brand.ifBlank { "Android device" },
            osLabel = osLabel,
            minecraftHint = "",
        )
    }

}
