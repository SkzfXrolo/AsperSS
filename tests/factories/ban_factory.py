from __future__ import annotations

import factory


class BanFactory(factory.DictFactory):
    player_uuid = factory.Faker("uuid4")
    player_name = factory.Faker("user_name")
    reason = factory.Iterator(["cheat", "killaura", "speed"])
    banned_at = factory.Faker("unix_time")
