from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def base_url():
    return os.getenv("ARGUS_BASE_URL", "http://127.0.0.1:8080")
