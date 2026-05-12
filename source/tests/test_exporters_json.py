import json
from exporters.json_pretty import export_json_pretty


def test_json_export_parseable():
    s = export_json_pretty({"issues_found": []})
    obj = json.loads(s)
    assert "metadata" in obj


def test_json_export_contains_scan():
    s = export_json_pretty({"issues_found": [{"tipo": "x"}]})
    obj = json.loads(s)
    assert "scan" in obj


def test_json_export_has_metadata():
    s = export_json_pretty({"issues_found": []})
    obj = json.loads(s)
    assert "metadata" in obj

