rule MimikatzBasicStringMatch
{
    meta:
        author = "argus-pack48"
        description = "Regla basica para strings frecuentes de mimikatz"
    strings:
        $a = "mimikatz" nocase
        $b = "sekurlsa::logonpasswords" nocase
        $c = "privilege::debug" nocase
    condition:
        any of them
}

