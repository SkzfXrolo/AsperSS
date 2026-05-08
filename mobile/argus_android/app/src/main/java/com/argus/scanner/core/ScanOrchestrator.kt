package com.argus.scanner.core

import android.content.Context
import android.os.Build
import android.provider.Settings
import com.argus.scanner.scanners.FileScanner
import com.argus.scanner.scanners.LauncherScanner
import com.argus.scanner.scanners.MemoryEditorScanner
import com.argus.scanner.scanners.PackageScanner
import com.argus.scanner.scanners.RootScanner
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn

/**
 * ScanOrchestrator — corre los 5 scanners del MVP en orden, agrega los
 * resultados, calcula risk score y los sube al backend Argus.
 *
 * Risk scoring (mapea con la convención del scanner desktop):
 *   CRITICAL hits  → +25 cada uno (cap +60)
 *   SOSPECHOSO     → +6  cada uno (cap +20)
 *   INFO           → +0
 *
 * Verdict derivado:
 *   ≥ 70 HACK
 *   ≥ 30 SOSPECHOSO
 *   else LIMPIO
 *
 * El backend recalcula con su propio ensemble (RF + heuristic + AI), así
 * que este score local es solo para mostrar al usuario antes del round-trip.
 */
class ScanOrchestrator(private val ctx: Context) {

    fun run(token: String): Flow<ScanProgressEvent> = flow {
        emit(ScanProgressEvent.Log("→ Argus Android · v1.6.49"))
        if (token.length < 8) {
            emit(ScanProgressEvent.Failed("Token inválido o demasiado corto"))
            return@flow
        }

        // 1) BackendClient — crear scan
        val client = BackendClient(token)
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

        // 2) PackageScanner (item #6 + #11)
        emit(ScanProgressEvent.Log("→ Revisando apps instaladas…"))
        val pkgs = try { PackageScanner(ctx).scan() } catch (e: Exception) {
            emit(ScanProgressEvent.Log("[!] PackageScanner falló: ${e.message}"))
            emptyList()
        }
        all += pkgs
        emit(ScanProgressEvent.Log("[OK] ${pkgs.size} hallazgo(s) en apps instaladas"))

        // 3) RootScanner (item #10)
        emit(ScanProgressEvent.Log("→ Detectando root / Magisk / Xposed…"))
        val root = try { RootScanner().scan() } catch (e: Exception) {
            emit(ScanProgressEvent.Log("[!] RootScanner falló: ${e.message}"))
            emptyList()
        }
        all += root
        emit(ScanProgressEvent.Log("[OK] ${root.size} signal(es) de root"))

        // 4) MemoryEditorScanner (item #11)
        emit(ScanProgressEvent.Log("→ Buscando memory editors / Game Guardian…"))
        val mem = try { MemoryEditorScanner(ctx).scan() } catch (e: Exception) {
            emit(ScanProgressEvent.Log("[!] MemoryEditorScanner falló: ${e.message}"))
            emptyList()
        }
        all += mem
        emit(ScanProgressEvent.Log("[OK] ${mem.size} hallazgo(s) en memory editors"))

        // 5) LauncherScanner (item #8)
        emit(ScanProgressEvent.Log("→ Inspeccionando launchers Minecraft móvil…"))
        val lnch = try { LauncherScanner(ctx).scan() } catch (e: Exception) {
            emit(ScanProgressEvent.Log("[!] LauncherScanner falló: ${e.message}"))
            emptyList()
        }
        all += lnch
        emit(ScanProgressEvent.Log("[OK] ${lnch.size} hallazgo(s) en launchers"))

        // 6) FileScanner (item #3 + #5 parcial)
        emit(ScanProgressEvent.Log("→ Revisando archivos sospechosos en /sdcard…"))
        val files = try { FileScanner(ctx).scan() } catch (e: Exception) {
            emit(ScanProgressEvent.Log("[!] FileScanner falló: ${e.message}"))
            emptyList()
        }
        all += files
        emit(ScanProgressEvent.Log("[OK] ${files.size} archivo(s) sospechoso(s)"))

        // 7) Score local (puro indicativo)
        val score = computeRiskScore(all)
        val verdict = when {
            score >= 70 -> "HACK_DETECTADO"
            score >= 30 -> "SOSPECHOSO"
            else        -> "LIMPIO"
        }
        emit(ScanProgressEvent.Log("→ Risk score local: $score · $verdict"))

        // 8) Subir al backend
        emit(ScanProgressEvent.Log("→ Enviando ${all.size} hallazgo(s) al panel…"))
        try {
            client.submitResults(scanId, all, score)
            emit(ScanProgressEvent.Log("[OK] Resultados subidos correctamente"))
            emit(ScanProgressEvent.Done(score, verdict))
        } catch (e: Exception) {
            emit(ScanProgressEvent.Failed("Error subiendo resultados: ${e.message}"))
        }
    }.flowOn(Dispatchers.IO)

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
