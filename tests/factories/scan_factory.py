from __future__ import annotations

import factory

from tests.factories.violation_factory import ViolationFactory


class ScanFactory(factory.DictFactory):
    id = factory.Sequence(lambda n: n + 1)
    machine_name = factory.Faker("hostname")
    minecraft_username = factory.Faker("user_name")
    risk_score = factory.Faker("pyint", min_value=0, max_value=100)
    verdict = factory.Iterator(["pending", "clean", "hack"])
    violations = factory.LazyFunction(lambda: [ViolationFactory() for _ in range(3)])
