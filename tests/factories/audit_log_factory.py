from __future__ import annotations

import factory


class AuditLogFactory(factory.DictFactory):
    actor = factory.Faker("user_name")
    action = factory.Iterator(["login", "logout", "ban", "feedback"])
    target = factory.Faker("user_name")
    created_at = factory.Faker("unix_time")
