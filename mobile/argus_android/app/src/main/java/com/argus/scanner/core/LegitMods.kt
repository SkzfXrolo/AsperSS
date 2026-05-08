package com.argus.scanner.core

/**
 * LegitMods — whitelist de mods/loaders legítimos para anti-FP.
 * Reusada por LauncherScanner cuando inspecciona /mods en PojavLauncher
 * y por FileScanner cuando ve .mcpack/.mcaddon.
 */
object LegitMods {

    // Mods Java conocidos legítimos (Pojav / Boardwalk)
    val JAVA_LEGIT_MOD_TERMS = listOf(
        "fabric-api", "fabric-loader", "fabric-mc",
        "forge-", "neoforge-",
        "optifine", "optifabric", "iris-",
        "sodium-", "sodium-extra", "sodium-android",
        "lithium-", "phosphor-", "starlight-",
        "ferritecore", "krypton-", "lazy-dfu",
        "jei-", "rei-", "emi-", "modmenu",
        "architectury", "cloth-config",
        "yacl", "midnightlib", "kotlin-for-forge",
        "geyser-", "floodgate-",
        "world-edit", "worldedit-",
        "shaderpack-", "complementary-shaders",
        "create-", "applied-energistics", "ae2-",
        "industrialcraft", "ic2-",
        "thaumcraft-", "botania-",
        // Common dependency libs
        "mixin-", "asmlib-", "yamcl-", "cit-resewn",
    )

    // Bedrock addons legítimos (.mcpack / .mcaddon firmados por Marketplace)
    val BEDROCK_LEGIT_TERMS = listOf(
        "behavior_pack", "resource_pack", "skin_pack",
        "world_template", "marketplace",
        "mojang_official", "vanilla",
    )

    fun isLegitJavaMod(filename: String): Boolean {
        val lower = filename.lowercase()
        return JAVA_LEGIT_MOD_TERMS.any { lower.contains(it) }
    }

    fun isLegitBedrockAddon(filename: String): Boolean {
        val lower = filename.lowercase()
        return BEDROCK_LEGIT_TERMS.any { lower.contains(it) }
    }
}
