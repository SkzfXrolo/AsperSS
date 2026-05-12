from __future__ import annotations

import factory


class ViolationFactory(factory.DictFactory):
    check_name = factory.Iterator(["reach", "killaura_no_swing", "autoclicker", "speed"])
    level = factory.Iterator(["LOW", "MID", "HIGH", "CRITICAL"])
    age_seconds = factory.Sequence(lambda n: (n % 120) + 1)
