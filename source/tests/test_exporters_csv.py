from exporters.csv_findings import export_csv_findings


def test_csv_has_header():
    out = export_csv_findings({"issues_found": []})
    assert "tipo,nombre,ruta,archivo,categoria,alerta,confidence" in out

