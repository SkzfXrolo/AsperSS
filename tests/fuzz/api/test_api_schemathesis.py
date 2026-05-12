from __future__ import annotations

import pathlib
import pytest
import schemathesis


SCHEMA = pathlib.Path("tests/contract/openapi.yaml")


@pytest.mark.fuzz
def test_openapi_schema_loads():
    if not SCHEMA.exists():
        pytest.skip("OpenAPI schema no disponible")
    schema = schemathesis.openapi.from_path(str(SCHEMA))
    assert schema is not None
