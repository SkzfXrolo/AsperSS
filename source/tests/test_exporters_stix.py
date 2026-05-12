from exporters.stix_export import export_to_stix


def test_stix_bundle_type():
    out = export_to_stix({"issues_found": []})
    assert out["type"] == "bundle"


def test_stix_has_objects():
    out = export_to_stix({"issues_found": [{"tipo": "a", "nombre": "b"}]})
    assert len(out["objects"]) == 1


def test_stix_indicator_fields():
    obj = export_to_stix({"issues_found": [{"tipo": "a", "nombre": "b"}]})["objects"][0]
    assert obj["type"] == "indicator"
    assert obj["spec_version"] == "2.1"


def test_stix_confidence_numeric():
    obj = export_to_stix({"issues_found": [{"tipo": "a", "nombre": "b", "confidence": 0.8}]})["objects"][0]
    assert isinstance(obj["confidence"], int)


def test_stix_empty_ignores_invalid():
    out = export_to_stix({"issues_found": ["x"]})
    assert out["objects"] == []

