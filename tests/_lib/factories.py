from __future__ import annotations

from tests.factories import ScanFactory, UserFactory, ViolationFactory


def make_user(**kwargs):
    return UserFactory(**kwargs)


def make_violation(**kwargs):
    return ViolationFactory(**kwargs)


def make_scan(**kwargs):
    return ScanFactory(**kwargs)
