import json
from exporters.json_export import export_to_json


def test_json_export_parseable():
    s = export_to_json({"issues_found": []})
    obj = json.loads(s)
    assert "metadata" in obj


def test_json_export_contains_scan():
    s = export_to_json({"issues_found": [{"tipo": "x"}]})
    obj = json.loads(s)
    assert "scan" in obj


def test_json_export_compact():
    s = export_to_json({"issues_found": []}, pretty=False)
    assert "\n" not in s

