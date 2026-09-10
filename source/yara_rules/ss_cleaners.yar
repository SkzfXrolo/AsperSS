rule SS_Forensic_Cleaner
{
    meta:
        author = "argus-v1.9"
        description = "Herramientas / scripts de wipe forense pre-SS"
    strings:
        $a = "fsutil usn deletejournal" nocase
        $b = "wevtutil cl" nocase
        $c = "Clear-EventLog" nocase
        $d = "Remove-Item -Recurse" nocase ascii
        $e = "prefetch" nocase
        $f = "AutomaticDestinations" nocase
        $g = "$Recycle.Bin" nocase
        $h = "ipconfig /flushdns" nocase
        $i = "vssadmin delete shadows" nocase
    condition:
        3 of them
}

rule SS_JVM_Attach_Injector
{
    meta:
        author = "argus-v1.9"
        description = "Attach API / agent load típico de injectores JVM"
    strings:
        $a = "VirtualMachine.attach" ascii
        $b = "loadAgent" ascii
        $c = "sun.tools.attach" ascii
        $d = "WindowsVirtualMachine" ascii
        $e = "com.sun.tools.attach" ascii
        $f = "agentmain" ascii
        $g = "premain" ascii
    condition:
        3 of them
}
