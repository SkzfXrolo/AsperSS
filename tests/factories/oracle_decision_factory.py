from __future__ import annotations

import factory


class OracleDecisionFactory(factory.DictFactory):
    score = factory.Faker("pyfloat", min_value=0, max_value=1)
    confidence = factory.Faker("pyfloat", min_value=0, max_value=1)
    action = factory.Iterator(["none", "watch", "ss", "kick", "ban"])
    reasoning = factory.Faker("sentence")
    top_factor = factory.Iterator(["reach MID", "killaura HIGH", "autoclicker LOW"])
