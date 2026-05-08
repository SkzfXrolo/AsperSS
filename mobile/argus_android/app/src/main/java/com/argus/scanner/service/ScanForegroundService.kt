package com.argus.scanner.service

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.argus.scanner.ArgusApp
import com.argus.scanner.MainActivity
import com.argus.scanner.R

/**
 * ScanForegroundService — item Android #12.
 *
 * Servicio en primer plano con notificación persistente mientras corre el
 * scan. Habilita 2 cosas críticas:
 *  1) MediaProjection (item #9) — Android obliga a tener un FGS de tipo
 *     `mediaProjection` activo ANTES de instanciar MediaProjection.
 *  2) Que el scan no muera si el usuario manda Argus a background o
 *     bloquea pantalla durante los ~30s de scan.
 *
 * No hace lógica del scan adentro: el scan corre en MainActivity con
 * Coroutines (Dispatchers.IO). Este servicio solo "sostiene" al proceso.
 *
 * Cómo se usa:
 *   ScanForegroundService.start(context)
 *   …scan…
 *   ScanForegroundService.stop(context)
 */
class ScanForegroundService : Service() {

    override fun onCreate() {
        super.onCreate()
        startAsForeground()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startAsForeground()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun startAsForeground() {
        val pi = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val notif: Notification = NotificationCompat
            .Builder(this, ArgusApp.SCAN_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(getString(R.string.fgs_notif_title))
            .setContentText(getString(R.string.fgs_notif_text))
            .setOngoing(true)
            .setContentIntent(pi)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            // Android 14+ requiere declarar el tipo del FGS.
            // Combinamos DATA_SYNC (scan general) + MEDIA_PROJECTION
            // (screenshot opcional). Si solo se usa DATA_SYNC y luego se
            // arranca screenshot el sistema rechaza, así que pedimos
            // ambos desde el principio.
            startForeground(
                NOTIF_ID, notif,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC or
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
            )
        } else {
            startForeground(NOTIF_ID, notif)
        }
    }

    companion object {
        private const val NOTIF_ID = 8801

        fun start(ctx: Context) {
            val intent = Intent(ctx, ScanForegroundService::class.java)
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    ctx.startForegroundService(intent)
                } else {
                    ctx.startService(intent)
                }
            } catch (_: Throwable) {
                // En API < 31 con app en background, startForegroundService
                // puede tirar IllegalStateException — no fatal.
            }
        }

        fun stop(ctx: Context) {
            try { ctx.stopService(Intent(ctx, ScanForegroundService::class.java)) }
            catch (_: Throwable) {}
        }
    }
}
