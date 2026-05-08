// Argus Android — root build
// AGP 8.2.x + Kotlin 1.9.x. Versions pinned conservadoramente para
// builds reproducibles desde Android Studio Hedgehog/Iguana o desde
// Gradle CLI con AGP compatible.

plugins {
    id("com.android.application") version "8.2.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.22" apply false
}
