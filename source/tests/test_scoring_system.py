from scoring_system import ScoringSystem


def test_legit_mod_low_score():
    sc = ScoringSystem()
    out = sc.calculate_score({
        "nombre": "sodium-0.5.8.jar",
        "archivo": r"C:\Users\x\AppData\Roaming\.minecraft\mods\sodium-0.5.8.jar",
        "ruta": r"C:\Users\x\AppData\Roaming\.minecraft\mods",
    })
    assert out["score"] < 30


def test_vape_high_name_score():
    sc = ScoringSystem()
    out = sc.calculate_score({
        "nombre": "vape-4.0.jar",
        "archivo": r"C:\Users\x\Downloads\vape-4.0.jar",
        "ruta": r"C:\Users\x\Downloads",
    })
    assert out["score"] >= 30
    assert out["alert_level"] in ("CRITICAL", "SOSPECHOSO", "POCO_SOSPECHOSO")
