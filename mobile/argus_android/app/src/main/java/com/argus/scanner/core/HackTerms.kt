package com.argus.scanner.core

/**
 * HackTerms — listas de detección móvil.
 *
 * Item Android #6, #8, #11. Embebido en la APK; en futuros packs se podrá
 * descargar dinámicamente desde el backend vía `/api/scanner-rules`.
 */
object HackTerms {

    // ── Cheat clients Bedrock (el .apk ES el cheat) ────────────────────────
    // Item #6 categoría a). package_name → label legible.
    val BEDROCK_CHEAT_PACKAGES = mapOf(
        "com.toolbox.box"            to "Toolbox for Minecraft PE",
        "com.tbox.box"               to "Toolbox (alt)",
        "me.kotmen.horion"           to "Horion launcher",
        "club.latite.mobile"         to "Latite Mobile",
        "dev.husky.client"           to "Husky Client",
        "com.husky.client"           to "Husky Client (alt)",
        "me.exodus.exodus"           to "Exodus",
        "com.exodus.client"          to "Exodus (alt)",
        "com.mcprestige.client"      to "Prestige",
        "com.catalysm.client"        to "Catalysm",
        "com.rebellion.client"       to "Rebellion",
        "com.flarehcf.client"        to "FlareHCF",
        "com.mcprohvh.client"        to "ProHvH",
        "com.moonclient.client"      to "Moon Client",
        "com.zephyrhcf.client"       to "Zephyr HCF",
        "com.mcfracture.client"      to "Fracture",
        "com.mcphantom.client"       to "Phantom",
    )

    // ── Memory editors / hack tools (item #6 categoría c, item #11) ────────
    val MEMORY_EDITOR_PACKAGES = mapOf(
        "com.MGGS"                   to "Game Guardian",
        "catch_.me_.if_you_can"      to "Game Guardian (forked)",
        "com.cih.gamecih2"           to "GameCIH 2",
        "com.cih.game_cih"           to "GameCIH",
        "bin.mt.plus"                to "MT Manager (APK editor)",
        "com.lc.lockplus"            to "Lucky Patcher",
        "io.va.exposed"              to "VirtualXposed",
        "com.parallel.intl.arm64"    to "Parallel Space",
        "com.lbe.parallel"           to "Parallel Space (alt)",
        "com.parallel.app"           to "Parallel Space (free)",
        "com.cih.creditcard"         to "CreditEdit (memory hack)",
    )

    // ── Root managers (item #6 categoría d, item #10) ──────────────────────
    val ROOT_MANAGER_PACKAGES = mapOf(
        "com.topjohnwu.magisk"               to "Magisk",
        "com.kingouser.com"                  to "KingoRoot",
        "eu.chainfire.supersu"               to "SuperSU",
        "com.koushikdutta.superuser"         to "Superuser",
        "org.lsposed.manager"                to "LSPosed Manager",
        "io.github.lsposed.manager"          to "LSPosed Manager (alt)",
        "de.robv.android.xposed.installer"   to "Xposed Installer",
        "me.weishu.exposed"                  to "EdXposed Manager",
        "me.weishu.kernelsu.manager"         to "KernelSU Manager",
        "com.tutk.kalay"                     to "iRoot",
    )

    // ── Launchers Minecraft móvil (item #8) ────────────────────────────────
    // Detección y categorización. NO son cheats por sí mismos pero su
    // presencia activa el escaneo de su carpeta de archivos.
    val MC_LAUNCHER_PACKAGES = mapOf(
        // Bedrock oficiales firmados por Mojang AB
        "com.mojang.minecraftpe"             to LauncherInfo("Minecraft Bedrock", LauncherKind.BEDROCK_OFFICIAL),
        "com.mojang.minecraftedu"            to LauncherInfo("Minecraft Education", LauncherKind.BEDROCK_OFFICIAL),
        "com.mojang.minecrafttrialpe"        to LauncherInfo("Minecraft Trial",     LauncherKind.BEDROCK_OFFICIAL),
        // Java vía Pojav
        "net.kdt.pojavlaunch"                to LauncherInfo("PojavLauncher",        LauncherKind.JAVA_POJAV),
        "net.kdt.pojavlauncher"              to LauncherInfo("PojavLauncher (alt)",  LauncherKind.JAVA_POJAV),
        "com.kdt.pojavlauncher"              to LauncherInfo("PojavLauncher (fork)", LauncherKind.JAVA_POJAV),
        // Boardwalk (Java forked)
        "com.boardwalk.boardwalk"            to LauncherInfo("Boardwalk Beta",   LauncherKind.JAVA_BOARDWALK),
        "org.boardwalk.merge"                to LauncherInfo("Boardwalk-merge",  LauncherKind.JAVA_BOARDWALK),
        // Bedrock launchers mod
        "com.mcpemaster.mcpe"                to LauncherInfo("MCPE Master",      LauncherKind.BEDROCK_MOD_LAUNCHER),
        "net.zhuoweizhang.mcpelauncher"      to LauncherInfo("BlockLauncher",    LauncherKind.BEDROCK_MOD_LAUNCHER),
        // HMCL móvil + Lithium
        "org.jackhuang.hmcl"                 to LauncherInfo("HMCL Android",     LauncherKind.JAVA_OTHER),
        "com.mclauncher.lithium"             to LauncherInfo("Lithium Launch",   LauncherKind.JAVA_OTHER),
    )

    // ── Hack-name terms (item #8 inspección de archivos) ───────────────────
    // Tokens que disparan match en filenames de .jar/.dex/.zip/.mcpack.
    // Mismo set conceptual que el scanner desktop, ajustado a móvil.
    // Word-boundary matching desde Kotlin.
    val HACK_TERMS = listOf(
        // Java desktop hacks (vía Pojav)
        "vape", "liquid", "wurst", "sigma", "impact", "meteor", "future",
        "salhack", "inertia", "astolfo", "rise", "drip", "rusherhack",
        "doomsday", "konas",
        // Bedrock specific
        "horion", "latite", "husky", "exodus", "prestige", "catalysm",
        "rebellion", "flarehcf", "prohvh", "moonclient", "zephyr",
        "fracture", "phantom", "moonlight", "argonclient", "azura",
        // Generic markers
        "killaura", "wallhack", "chams", "esp", "aimbot", "tracers",
        "x-ray", "xray", "fly hack", "flyhack", "speedhack", "nofall",
        "autoclick", "reach hack", "reachhack", "scaffold", "criticals",
        "killauraclient", "fastbreak",
        // Memory editor scripts
        "gamehack", "gameguardian", "ggscript", "memoryhack",
    )

    // ── Tokens Bayesian ligero (item #15 anti-FP móvil) ────────────────────
    val BAYES_NEGATIVE = listOf(
        "adaway", "viper4android", "appbutton", "audiomod",
        "customclock", "lawnchair", "nova launcher", "kustom",
        "tasker", "kwgt", "kwlp", "battery saver",
    )
    val BAYES_POSITIVE = listOf(
        "killaura", "horion", "latite", "husky", "exodus", "prestige",
        "gameguardian", "mcaim", "mcesp", "wallhack",
    )
}

data class LauncherInfo(val displayName: String, val kind: LauncherKind)
enum class LauncherKind {
    BEDROCK_OFFICIAL,        // com.mojang.* — verificar firma Mojang AB
    BEDROCK_MOD_LAUNCHER,    // MCPE Master, BlockLauncher
    JAVA_POJAV,              // PojavLauncher (legítimo, pero inspeccionar mods)
    JAVA_BOARDWALK,
    JAVA_OTHER,              // HMCL, Lithium Launch
}
