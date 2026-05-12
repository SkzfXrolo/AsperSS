from exporters.sarif import export_sarif


def test_sarif_structure():
    out = export_sarif({"issues_found": [{"tipo": "x", "nombre": "n"}]})
    assert out["version"] == "2.1.0"
    assert "runs" in out

