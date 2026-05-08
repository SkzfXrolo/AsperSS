package com.argus.scanner.scanners

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.util.Base64
import android.view.Display
import android.view.WindowManager
import com.argus.scanner.service.ScanForegroundService
import kotlinx.coroutines.suspendCancellableCoroutine
import java.io.ByteArrayOutputStream
import kotlin.coroutines.resume

/**
 * ScreenshotCapture — item Android #9.
 *
 * Captura UN frame del display primario usando MediaProjection API.
 * Requiere consent dialog del SO ("Argus quiere capturar tu pantalla")
 * que el usuario debe aceptar — NO se puede skipear ni cachear.
 *
 * Pre-requisito: ScanForegroundService corriendo (Android 14+ exige FGS
 * de tipo `mediaProjection` activo antes de instanciar MediaProjection).
 *
 * Output: PNG comprimido a 70% calidad → base64 string del mismo formato
 * que Windows/Linux para uniformidad en el panel.
 *
 * Uso:
 *   1) En la Activity: launch un ActivityResultContract.StartActivityForResult
 *      con MediaProjectionManager.createScreenCaptureIntent(). Guardar
 *      el resultCode + data del callback.
 *   2) Llamar ScreenshotCapture(ctx).captureToBase64(resultCode, data).
 */
class ScreenshotCapture(private val ctx: Context) {

    /** Crea el intent del consent dialog. */
    fun buildConsentIntent(): Intent {
        val mpm = ctx.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
                as MediaProjectionManager
        return mpm.createScreenCaptureIntent()
    }

    /**
     * Toma UN frame y lo devuelve como string base64 PNG.
     * Devuelve null si falla cualquier paso.
     */
    suspend fun captureToBase64(resultCode: Int, data: Intent?): String? {
        if (data == null) return null
        // FGS debe estar arriba ANTES de crear MediaProjection (API 34+).
        // El caller debería haberlo arrancado, pero por seguridad lo
        // re-arrancamos aquí.
        ScanForegroundService.start(ctx)

        val mpm = ctx.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
                as MediaProjectionManager
        val mp: MediaProjection = try {
            mpm.getMediaProjection(resultCode, data) ?: return null
        } catch (_: Throwable) { return null }

        return try {
            captureOnce(mp)
        } finally {
            try { mp.stop() } catch (_: Throwable) {}
        }
    }

    private suspend fun captureOnce(mp: MediaProjection): String? {
        val (w, h, dpi) = pickDisplayMetrics()
        if (w <= 0 || h <= 0) return null

        val reader = ImageReader.newInstance(w, h, PixelFormat.RGBA_8888, 2)
        val handlerThread = HandlerThread("argus-screenshot").apply { start() }
        val handler = Handler(handlerThread.looper)

        // API 34: registrar callback obligatorio.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            try {
                mp.registerCallback(object : MediaProjection.Callback() {}, handler)
            } catch (_: Throwable) {}
        }

        var virtualDisplay: VirtualDisplay? = null
        try {
            virtualDisplay = mp.createVirtualDisplay(
                "argus-cap",
                w, h, dpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                reader.surface, null, handler
            )
            return suspendCancellableCoroutine { cont ->
                val listener = ImageReader.OnImageAvailableListener { rdr ->
                    var img: Image? = null
                    try {
                        img = rdr.acquireLatestImage() ?: return@OnImageAvailableListener
                        val bmp = imageToBitmap(img, w, h)
                        val baos = ByteArrayOutputStream()
                        bmp.compress(Bitmap.CompressFormat.PNG, 70, baos)
                        bmp.recycle()
                        val b64 = Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP)
                        if (cont.isActive) cont.resume(b64)
                    } catch (t: Throwable) {
                        if (cont.isActive) cont.resume(null)
                    } finally {
                        try { img?.close() } catch (_: Throwable) {}
                    }
                }
                reader.setOnImageAvailableListener(listener, handler)
                cont.invokeOnCancellation {
                    try { reader.setOnImageAvailableListener(null, null) } catch (_: Throwable) {}
                }
            }
        } finally {
            try { virtualDisplay?.release() } catch (_: Throwable) {}
            try { reader.close() } catch (_: Throwable) {}
            try { handlerThread.quitSafely() } catch (_: Throwable) {}
        }
    }

    private fun pickDisplayMetrics(): Triple<Int, Int, Int> {
        val wm = ctx.getSystemService(Context.WINDOW_SERVICE) as? WindowManager
            ?: return Triple(0, 0, 0)
        val dm = ctx.getSystemService(Context.DISPLAY_SERVICE) as? DisplayManager
        val display: Display? = dm?.getDisplay(Display.DEFAULT_DISPLAY)
            ?: @Suppress("DEPRECATION") wm.defaultDisplay
        val metrics = ctx.resources.displayMetrics
        // Cap a 1080x2400 para mantener PNG razonablemente pequeño en
        // pantallas QHD+.
        val w = metrics.widthPixels.coerceAtMost(1080)
        val h = metrics.heightPixels.coerceAtMost(2400)
        val dpi = metrics.densityDpi
        // Suprime warning cuando sí usamos display.
        display?.let { /* no-op */ }
        return Triple(w, h, dpi)
    }

    private fun imageToBitmap(image: Image, w: Int, h: Int): Bitmap {
        val plane = image.planes[0]
        val buffer = plane.buffer
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        val rowPadding = rowStride - pixelStride * w
        val bmp = Bitmap.createBitmap(
            w + rowPadding / pixelStride, h, Bitmap.Config.ARGB_8888
        )
        bmp.copyPixelsFromBuffer(buffer)
        // Crop al ancho real (descartar padding).
        return if (rowPadding == 0) bmp
        else Bitmap.createBitmap(bmp, 0, 0, w, h).also { if (it !== bmp) bmp.recycle() }
    }
}
