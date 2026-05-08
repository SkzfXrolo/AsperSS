# Argus Android — ProGuard rules para release.
# Mantenemos las clases de scanners completas para que la reflexión y los
# logs sean legibles en caso de crash report.

-keep class com.argus.scanner.** { *; }
-keep class com.argus.scanner.scanners.** { *; }
-keep class com.argus.scanner.core.** { *; }

# Compose
-dontwarn androidx.compose.**

# Kotlin coroutines
-keepclassmembernames class kotlinx.** { volatile <fields>; }

# Logs en release: mantener nombres pero remover Log.d/v
-assumenosideeffects class android.util.Log {
    public static int d(...);
    public static int v(...);
}
