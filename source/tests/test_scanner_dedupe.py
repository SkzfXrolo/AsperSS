from scanner_dedupe import dedupe_issues


def test_dedupe_removes_identical_issues():
    issues = [
        {"tipo": "blacklisted_mod", "ruta": r"C:\a\mods\vape.jar", "nombre": "vape"},
        {"tipo": "blacklisted_mod", "ruta": r"C:\a\mods\vape.jar", "nombre": "vape"},
        {"tipo": "jar_file", "ruta": r"C:\b\x.jar", "nombre": "otro"},
    ]
    out = dedupe_issues(issues)
    assert len(out) == 2
