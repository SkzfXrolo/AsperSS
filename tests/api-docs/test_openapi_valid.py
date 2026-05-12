from __future__ import annotations

import pathlib

import yaml


def test_openapi_yaml_is_valid():
    p = pathlib.Path("tests/contract/openapi.yaml")
    assert p.exists()
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert doc.get("openapi", "").startswith("3.")
