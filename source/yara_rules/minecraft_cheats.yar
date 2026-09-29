rule MC_VapeClient_Strings
{
    meta:
        author = "argus-v1.8"
        description = "Strings frecuentes de Vape / clientes inject"
    strings:
        $a = "vape.gg" nocase
        $b = "VapeLite" nocase
        $c = "Vape V4" nocase
        $d = "me/vape/" nocase
        $e = "VapeClient" nocase
    condition:
        2 of them
}

rule MC_Injector_Bypass
{
    meta:
        author = "argus-v1.8"
        description = "Injectores / attach a JVM / bypass tipicos"
    strings:
        $a = "VirtualAllocEx" ascii wide
        $b = "WriteProcessMemory" ascii wide
        $c = "CreateRemoteThread" ascii wide
        $d = "jvm.dll" nocase
        $e = "Java_sun_tools_attach" ascii
        $f = "attachListener" nocase
        $g = "InstrumentationImpl" ascii
    condition:
        3 of them
}

rule MC_GhostClient_Pack
{
    meta:
        author = "argus-v1.8"
        description = "Nombres / paquetes de ghost clients MC"
    strings:
        $a = "liquidbounce" nocase
        $b = "wurstclient" nocase
        $c = "impactclient" nocase
        $d = "aristois" nocase
        $e = "meteor-client" nocase
        $f = "raven.b+" nocase
        $g = "rise client" nocase
        $h = "sigma5" nocase
    condition:
        any of them
}

rule MC_SelfDestruct_Cleaner
{
    meta:
        author = "argus-v1.8"
        description = "Strings de self-destruct / wipe forense usados en cheats"
    strings:
        $a = "selfdestruct" nocase
        $b = "prefetch" nocase
        $c = "Wevtutil" nocase
        $d = "Clear-EventLog" nocase
        $e = "fsutil usn deletejournal" nocase
        $f = "Recent\\AutomaticDestinations" nocase
    condition:
        3 of them
}

rule MC_Meteor_Wurst_Rise
{
    meta:
        author = "argus-v1.9"
        description = "Meteor / Wurst / Rise client package paths"
    strings:
        $a = "meteordevelopment" nocase
        $b = "meteor-client" nocase
        $c = "net/wurstclient" nocase
        $d = "me/zeroeightsix/kami" nocase
        $e = "rise/client" nocase
        $f = "intent/cloudflare" nocase ascii
        $g = "baritone/api" nocase
        $h = "cabaletta/baritone" nocase
    condition:
        2 of them
}

rule MC_Raven_Myau_Drip
{
    meta:
        author = "argus-v1.9"
        description = "Raven / Myau / Drip / ghost clicker strings"
    strings:
        $a = "keystrokesmod" nocase
        $b = "raven.b+" nocase
        $c = "myau.client" nocase
        $d = "drip.client" nocase
        $e = "GhostClicker" nocase
        $f = "AutoClicker" ascii
        $g = "ReachModule" nocase
        $h = "VelocityModule" nocase
    condition:
        2 of them
}

rule MC_Forge_Mixin_Inject
{
    meta:
        author = "argus-v1.9"
        description = "Mixin / agent injection markers in non-mod jars"
    strings:
        $a = "org/spongepowered/asm/mixin" ascii
        $b = "LunarTweaker" nocase
        $c = "TransformerManager" ascii
        $d = "retransformClasses" ascii
        $e = "addTransformer" ascii
        $f = "sun/tools/attach/WindowsVirtualMachine" ascii
    condition:
        3 of them
}

rule MC_Thunder_Doomsday_Weave
{
    meta:
        author = "argus-v1.9"
        description = "ThunderHack / Doomsday / Weave loader markers"
    strings:
        $a = "thunderhack" nocase
        $b = "doomsday" nocase
        $c = "weave.loader" nocase
        $d = "weaveloader" nocase
        $e = "dev/lvstrng" nocase
        $f = "me/alphaoleg/doomsday" nocase
        $g = "cc/thhack" nocase
        $h = "net/weavemc" nocase
    condition:
        2 of them
}

rule MC_Aristois_Tenacity_Konas
{
    meta:
        author = "argus-v1.9"
        description = "Aristois / Tenacity / Konas / Novoline strings"
    strings:
        $a = "aristois" nocase
        $b = "tenacity" nocase
        $c = "konas" nocase
        $d = "novoline" nocase
        $e = "exhibition" nocase
        $f = "whiteout" nocase
        $g = "astolfo" nocase
        $h = "entropy.client" nocase
    condition:
        2 of them
}
