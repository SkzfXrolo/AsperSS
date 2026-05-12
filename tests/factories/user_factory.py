from __future__ import annotations

import factory


class UserFactory(factory.DictFactory):
    id = factory.Sequence(lambda n: n + 1)
    username = factory.Faker("user_name")
    email = factory.Faker("email")
    company_id = 1
    roles = ["user"]
