from __future__ import annotations

import factory


class UserFactory(factory.DictFactory):
    id = factory.Sequence(lambda n: n + 1)
    username = factory.Sequence(lambda n: f"user{n}")
    roles = ["viewer"]
    company_id = 1
