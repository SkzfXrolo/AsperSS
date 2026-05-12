from __future__ import annotations

import pytest

from tests._lib.factories import make_scan, make_user


@pytest.fixture
def sample_user():
    return make_user()


@pytest.fixture
def sample_scan():
    return make_scan()
