// Argus Android — app module
// minSdk = 26 (Android 8) por UsageStatsManager confiable.
// targetSdk = 34 (Android 14).
// Compose UI minimalista. Sin OkHttp ni Gson — usamos
// HttpURLConnection + org.json para mantener APK liviano (<8MB target).

import java.text.SimpleDateFormat
import java.util.Date
import java.util.TimeZone

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// ── Item Android #15 — meta-build leído del environment de CI ───────────
// Se inyecta en BuildConfig para que la app conozca su propio commit y
// pueda comparar contra /api/android-version (auto-updater).
val argusBuildCommit: String = (System.getenv("ARGUS_BUILD_COMMIT") ?: "dev").let {
    if (it.length >= 7) it.substring(0, 7) else it
}
val argusBuildNumber: Int = (System.getenv("ARGUS_BUILD_NUMBER") ?: "1").toIntOrNull() ?: 1
val argusBuildTimestamp: String = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'").apply {
    timeZone = TimeZone.getTimeZone("UTC")
}.format(Date())

android {
    namespace = "com.argus.scanner"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.argus.scanner"
        minSdk        = 26
        targetSdk     = 34
        // versionCode debe incrementarse en cada release CI; usamos
        // github.run_number como source-of-truth, default 1 en local.
        versionCode   = argusBuildNumber
        versionName   = "1.6.49"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables { useSupportLibrary = true }

        // Backend URL; override con BuildConfig para builds dev/release.
        buildConfigField("String", "ARGUS_API_BASE",
            "\"https://asperss.onrender.com\"")
        buildConfigField("String", "ARGUS_BUILD_COMMIT",
            "\"$argusBuildCommit\"")
        buildConfigField("String", "ARGUS_BUILD_TIMESTAMP",
            "\"$argusBuildTimestamp\"")
    }

    // ── Item Android #15 — signing config self-signed ──────────────────
    // El keystore lo provee el workflow CI. En local sin env vars, el
    // build sigue funcionando con la signing config debug por default.
    val keystorePathEnv = System.getenv("ARGUS_KEYSTORE_PATH")
    val keystorePassEnv = System.getenv("ARGUS_KEYSTORE_PASS")
    val keyAliasEnv     = System.getenv("ARGUS_KEY_ALIAS")
    val keyPassEnv      = System.getenv("ARGUS_KEY_PASS")
    val hasReleaseKey   = !keystorePathEnv.isNullOrBlank() &&
                          !keystorePassEnv.isNullOrBlank() &&
                          !keyAliasEnv.isNullOrBlank() &&
                          !keyPassEnv.isNullOrBlank() &&
                          file(keystorePathEnv!!).exists()

    signingConfigs {
        if (hasReleaseKey) {
            create("release") {
                storeFile     = file(keystorePathEnv!!)
                storePassword = keystorePassEnv
                keyAlias      = keyAliasEnv
                keyPassword   = keyPassEnv
                // v1+v2+v3 schemes habilitados explícitamente. Algunos OEM
                // (Honor MagicOS, Huawei EMUI, Xiaomi MIUI) rechazan APKs
                // firmados solo con v3 con el genérico "el paquete no es
                // válido" durante el sideload. Con v1+v2 garantizamos
                // compat con Android 7+ side-load workflows.
                enableV1Signing = true
                enableV2Signing = true
                enableV3Signing = true
            }
        }
    }

    buildTypes {
        release {
            // Pack 27 hotfix — minify+shrink desactivado para descartar R8
            // como causa de "el paquete no es válido". Costo: APK pasa de
            // ~1.3 MB a ~3-4 MB, aceptable para ahorrarnos un round de
            // bug-hunting de proguard rules de Compose. Re-habilitamos
            // selectivamente cuando el flow esté validado en producción.
            isMinifyEnabled    = false
            isShrinkResources  = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            if (hasReleaseKey) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
        debug {
            isMinifyEnabled = false
            applicationIdSuffix = ".debug"
            versionNameSuffix   = "-debug"
            // Opcional: backend de staging/local
            // buildConfigField("String", "ARGUS_API_BASE", "\"http://10.0.2.2:5000\"")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.10"
    }

    packaging {
        resources {
            excludes += setOf(
                "/META-INF/{AL2.0,LGPL2.1}",
                "/META-INF/DEPENDENCIES",
                "/META-INF/LICENSE*",
                "/META-INF/NOTICE*"
            )
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")

    // Compose BOM — versiones consistentes.
    val composeBom = platform("androidx.compose:compose-bom:2024.02.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // Coroutines (HTTP off-main, file scan off-main).
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

    // Tests (opcionales, no entran en release).
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation(composeBom)
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
