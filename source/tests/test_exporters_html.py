from exporters.html_report import export_html_report


def test_html_contains_table():
    out = export_html_report({"issues_found": [{"tipo": "x", "nombre": "n", "ruta": "r", "alerta": "SOSPECHOSO"}]})
    assert "<table" in out and "Argus Report" in out

