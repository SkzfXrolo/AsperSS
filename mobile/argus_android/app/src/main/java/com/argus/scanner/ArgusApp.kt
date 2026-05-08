package com.argus.scanner

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

/**
 * Argus Android — Application class.
 *
 * Item Android #1: punto de entrada de la APK. Solo registra el canal de
 * notificaciones del Foreground Service (item #9, MediaProjection requiere
 * notificación visible).
 */
class ArgusApp : Application() {
    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            val ch = NotificationChannel(
                getString(R.string.fgs_channel_id),
                getString(R.string.fgs_channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Notificación visible mientras Argus escanea el dispositivo."
                setShowBadge(false)
            }
            nm.createNotificationChannel(ch)
        }
    }
}
