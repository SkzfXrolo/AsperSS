package com.argus.scanner

import android.Manifest
import android.app.AppOpsManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import com.argus.scanner.ui.ScanScreen

/**
 * MainActivity — entrada de la APK Argus Android.
 *
 * Pack 25:
 *   1) Onboarding con permisos minimum-necessary (item #14).
 *   2) Input de token + botón "Iniciar scan".
 *   3) Pantalla de progreso con log en vivo de scanners.
 *   4) Resultado final con risk score + botón "Ver en panel".
 *
 * Pack 26:
 *   - Pide consent de MediaProjection al iniciar scan (item #9).
 *     Si el usuario lo niega, el scan sigue pero sin screenshot.
 *   - Soporta deeplink argus://scan?token=XXX para auto-fill desde
 *     bot Discord / link compartido.
 */
class MainActivity : ComponentActivity() {

    private var initialToken: String = ""

    /** Resultados de MediaProjection consent. Se pasan al orchestrator. */
    private var pendingScreenshotResultCode: Int = 0
    private var pendingScreenshotData: Intent? = null
    private var screenshotConsentCallback: ((Int, Intent?) -> Unit)? = null

    private val mediaProjectionLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            pendingScreenshotResultCode = result.resultCode
            pendingScreenshotData = result.data
            screenshotConsentCallback?.invoke(result.resultCode, result.data)
            screenshotConsentCallback = null
        }

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
                requestScreenshotConsent = ::requestScreenshotConsent,
                getPendingScreenshot = { pendingScreenshotResultCode to pendingScreenshotData },
                clearScreenshot = {
                    pendingScreenshotResultCode = 0
                    pendingScreenshotData = null
                },
            )
        }
    }

    // ── Storage permission ────────────────────────────────────────────────
    private fun hasStoragePermission(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
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

    // ── UsageStats permission ──────────────────────────────────────────────
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
            startActivity(Intent(Settings.ACTION_SETTINGS))
        }
    }

    // ── MediaProjection consent (item #9) ──────────────────────────────────
    /**
     * Lanza el consent dialog del SO. callback recibe (resultCode, data).
     * Si el usuario acepta resultCode=Activity.RESULT_OK y data != null.
     * Si lo niega, data == null. El scan en cualquier caso sigue.
     */
    private fun requestScreenshotConsent(callback: (Int, Intent?) -> Unit) {
        screenshotConsentCallback = callback
        try {
            val mpm = getSystemService(Context.MEDIA_PROJECTION_SERVICE)
                    as MediaProjectionManager
            mediaProjectionLauncher.launch(mpm.createScreenCaptureIntent())
        } catch (_: Throwable) {
            callback(0, null)
            screenshotConsentCallback = null
        }
    }
}
