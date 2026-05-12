from __future__ import annotations

import factory


class ScanFactory(factory.DictFactory):
    id = factory.Sequence(lambda n: n + 1)
    player_name = factory.Sequence(lambda n: f"player{n}")
    score = 0.5
    violations = []
