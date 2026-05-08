package com.argus.scanner.scanners

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.content.pm.Signature
import android.os.Build
import com.argus.scanner.core.HackTerms
import com.argus.scanner.core.ScanResult
import com.argus.scanner.core.smartHackMatch
import java.security.MessageDigest

/**
 * PackageScanner — items #6 (cheat clients), #11 (memory editors).
 *
 * Recorre PackageManager.getInstalledPackages buscando paquetes de la
 * blacklist. Reporta cada match con:
 *  - package name
 *  - app label
 *  - version + version code
 *  - install source (Play Store / sideload / desconocido)
 *  - first install time
 *  - signing cert SHA-256
 *
 * También busca tokens HACK_TERMS en el label (UI name) por si hay un
 * fork rebrandeado fuera de la blacklist (ej. "Horion 2024 Edition" no
 * coincidiría por package_name pero sí por label).
 */
class PackageScanner(private val ctx: Context) {

    fun scan(): List<ScanResult> {
        val pm = ctx.packageManager
        val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
            PackageManager.GET_SIGNING_CERTIFICATES or PackageManager.MATCH_UNINSTALLED_PACKAGES
        else
            @Suppress("DEPRECATION")
            PackageManager.GET_SIGNATURES or PackageManager.MATCH_UNINSTALLED_PACKAGES

        val pkgs: List<PackageInfo> = try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
                pm.getInstalledPackages(PackageManager.PackageInfoFlags.of(flags.toLong()))
            else
                @Suppress("DEPRECATION")
                pm.getInstalledPackages(flags)
        } catch (e: Exception) {
            return emptyList()
        }

        val results = mutableListOf<ScanResult>()

        for (info in pkgs) {
            val name  = info.packageName ?: continue
            // compileSdk 34 expone PackageInfo.applicationInfo como @Nullable.
            // Necesitamos capturar a local val para que el smart-cast funcione,
            // y caer a packageName si por alguna razón es null.
            val appInfo = info.applicationInfo
            val label = if (appInfo != null) {
                try { pm.getApplicationLabel(appInfo).toString() } catch (_: Exception) { name }
            } else name
            val verName = info.versionName ?: ""

            // 1) Blacklist directa por package name
            HackTerms.BEDROCK_CHEAT_PACKAGES[name]?.let { hit ->
                results += build(
                    name, label, verName, info,
                    pm = pm,
                    tipo = "CHEAT_APP_BEDROCK",
                    desc = "Cheat client Bedrock detectado: $hit",
                    alerta = "CRITICAL",
                    confidence = 0.92,
                    detected = listOf("blacklist:$name", "label:$hit")
                )
            }
            HackTerms.MEMORY_EDITOR_PACKAGES[name]?.let { hit ->
                results += build(
                    name, label, verName, info,
                    pm = pm,
                    tipo = "MEMORY_EDITOR",
                    desc = "Memory editor / hack tool detectado: $hit",
                    alerta = "CRITICAL",
                    confidence = 0.85,
                    detected = listOf("memhack:$name", "label:$hit")
                )
            }
            HackTerms.ROOT_MANAGER_PACKAGES[name]?.let { hit ->
                // Root manager NO es CRITICAL automático — el usuario puede
                // ser dev legítimo. SOSPECHOSO con confidence baja.
                results += build(
                    name, label, verName, info,
                    pm = pm,
                    tipo = "ROOT_TOOL",
                    desc = "Root/Xposed manager detectado: $hit",
                    alerta = "SOSPECHOSO",
                    confidence = 0.45,
                    detected = listOf("rootmgr:$name", "label:$hit")
                )
            }

            // 2) Match por label (fork rebrand) — solo si no es ya blacklisted
            val alreadyHit = name in HackTerms.BEDROCK_CHEAT_PACKAGES
                          || name in HackTerms.MEMORY_EDITOR_PACKAGES
            if (!alreadyHit) {
                for (term in HackTerms.HACK_TERMS) {
                    if (smartHackMatch(label, term) || smartHackMatch(name, term)) {
                        results += build(
                            name, label, verName, info,
                            pm = pm,
                            tipo = "CHEAT_APP_HEURISTIC",
                            desc = "App con nombre que contiene '$term'",
                            alerta = "SOSPECHOSO",
                            confidence = 0.55,
                            detected = listOf("term:$term", "name:$name")
                        )
                        break
                    }
                }
            }
        }
        return results
    }

    private fun build(
        pkg: String, label: String, ver: String, info: PackageInfo,
        pm: PackageManager,
        tipo: String, desc: String, alerta: String,
        confidence: Double, detected: List<String>,
    ): ScanResult {
        val installSrc = try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R)
                pm.getInstallSourceInfo(pkg).installingPackageName
            else
                @Suppress("DEPRECATION") pm.getInstallerPackageName(pkg)
        } catch (_: Exception) { null }

        val sigSha = try { signingCertSha256(info) } catch (_: Exception) { null }

        val descFull = buildString {
            append(desc)
            append(" · pkg=").append(pkg)
            if (ver.isNotBlank()) append(" v").append(ver)
            installSrc?.let { append(" · install=").append(it) }
            sigSha?.let { append(" · sig=").append(it.take(12)).append("…") }
        }
        val patterns = detected.toMutableList()
        installSrc?.let { patterns += "src:$it" }
        sigSha?.let     { patterns += "sig:${it.take(16)}" }

        return ScanResult(
            tipo = tipo,
            categoria = if (alerta == "CRITICAL") "CRITICAL" else "SOSPECHOSO",
            nombre = label,
            ruta = pkg,
            descripcion = descFull,
            confidence = confidence,
            alerta = alerta,
            detected_patterns = patterns,
            file_hash = sigSha,
        )
    }

    private fun signingCertSha256(info: PackageInfo): String? {
        val sigs: Array<Signature>? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            info.signingInfo?.let {
                if (it.hasMultipleSigners()) it.apkContentsSigners else it.signingCertificateHistory
            }
        } else {
            @Suppress("DEPRECATION") info.signatures
        }
        if (sigs.isNullOrEmpty()) return null
        val md = MessageDigest.getInstance("SHA-256")
        md.update(sigs[0].toByteArray())
        return md.digest().joinToString("") { "%02x".format(it) }
    }
}
