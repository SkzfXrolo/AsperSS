from __future__ import annotations

import factory


class CompanyFactory(factory.DictFactory):
    id = factory.Sequence(lambda n: n + 1)
    name = factory.Sequence(lambda n: f"company{n}")
    plan = "free"
