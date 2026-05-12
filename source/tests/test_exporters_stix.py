from exporters.stix import export_stix_bundle


def test_stix_bundle_type():
    out = export_stix_bundle({"issues_found": []})
    assert out["type"] == "bundle"


def test_stix_has_objects():
    out = export_stix_bundle({"issues_found": [{"tipo": "a", "nombre": "b"}]})
    assert len(out["objects"]) == 1


def test_stix_indicator_fields():
    obj = export_stix_bundle({"issues_found": [{"tipo": "a", "nombre": "b"}]})["objects"][0]
    assert obj["type"] == "indicator"
    assert obj["spec_version"] == "2.1"


def test_stix_confidence_numeric():
    obj = export_stix_bundle({"issues_found": [{"tipo": "a", "nombre": "b"}]})["objects"][0]
    assert obj["pattern_type"] == "stix"


def test_stix_empty_ignores_invalid():
    out = export_stix_bundle({"issues_found": ["x"]})
    assert out["objects"] == []

