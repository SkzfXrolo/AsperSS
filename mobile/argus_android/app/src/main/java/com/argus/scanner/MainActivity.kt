package com.argus.scanner

import android.Manifest
import android.app.AppOpsManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.argus.scanner.ui.ScanScreen

/**
 * MainActivity — entrada de la APK Argus Android.
 *
 * UI minimalista en Compose (item #1):
 *   1) Onboarding con permisos minimum-necessary (item #14).
 *   2) Input de token + botón "Iniciar scan".
 *   3) Pantalla de progreso con log en vivo de scanners.
 *   4) Resultado final con risk score + botón "Ver en panel".
 *
 * Soporta deeplink argus://scan?token=XXX (preconfigura el token desde un
 * link compartido por Discord/Telegram).
 */
class MainActivity : ComponentActivity() {

    private var initialToken: String = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Deeplink — argus://scan?token=XXX
        intent?.data?.let { uri ->
            if (uri.scheme == "argus" && uri.host == "scan") {
                initialToken = uri.getQueryParameter("token") ?: ""
            }
        }

        setContent {
            ScanScreen(
                initialToken = initialToken,
                hasStorage   = ::hasStoragePermission,
                hasUsage     = ::hasUsageStatsPermission,
                requestStorage = ::requestStoragePermission,
                requestUsage   = ::requestUsageStatsPermission,
            )
        }
    }

    // ── Storage permission ────────────────────────────────────────────────
    private fun hasStoragePermission(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // Android 11+: MANAGE_EXTERNAL_STORAGE (special permission).
            return Environment.isExternalStorageManager()
        }
        return ContextCompat.checkSelfPermission(
            this, Manifest.permission.READ_EXTERNAL_STORAGE
        ) == PackageManager.PERMISSION_GRANTED
    }

    private val legacyStoragePermLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { /* re-render por LaunchedEffect */ }

    private fun requestStoragePermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            try {
                val intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                    .setData(Uri.parse("package:$packageName"))
                startActivity(intent)
            } catch (_: Exception) {
                startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
            }
        } else {
            legacyStoragePermLauncher.launch(Manifest.permission.READ_EXTERNAL_STORAGE)
        }
    }

    // ── UsageStats permission (item #4 / #7) ──────────────────────────────
    // Es un AppOps permission, no runtime — el usuario lo concede en
    // Settings > Apps > Special access > Usage access.
    private fun hasUsageStatsPermission(): Boolean {
        val appOps = getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            appOps.unsafeCheckOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                android.os.Process.myUid(), packageName
            )
        } else {
            @Suppress("DEPRECATION")
            appOps.checkOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                android.os.Process.myUid(), packageName
            )
        }
        return mode == AppOpsManager.MODE_ALLOWED
    }

    private fun requestUsageStatsPermission() {
        try {
            startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
        } catch (_: Exception) {
            // Algunas ROMs no exponen el intent — fallback al settings principal.
            startActivity(Intent(Settings.ACTION_SETTINGS))
        }
    }
}
