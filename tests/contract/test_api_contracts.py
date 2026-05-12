from __future__ import annotations

import os

import pytest
import requests
import schemathesis
from hypothesis import settings


SCHEMA = schemathesis.openapi.from_path("tests/contract/openapi.yaml")


@pytest.mark.contract
@SCHEMA.parametrize()
@settings(max_examples=5, deadline=None)
def test_api_contract(case):
    base_url = os.getenv("ARGUS_BASE_URL", "http://127.0.0.1:8080")
    try:
        requests.get(f"{base_url}/health", timeout=3)
    except Exception:
        pytest.skip("Servidor no disponible para contract tests")
    response = case.call(base_url=base_url)
    case.validate_response(response)
