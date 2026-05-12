from __future__ import annotations

import factory


class ViolationFactory(factory.DictFactory):
    check_name = "speed_a"
    level = "LOW"
    age_seconds = 2
